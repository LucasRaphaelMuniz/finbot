"""
services/importacao.py — importação de fatura de cartão (Fase 5.3 do
PLANO_EXECUCAO.md). Fluxo em 3 passos, nada entra no banco antes da
confirmação explícita do usuário (requisito do plano):

1. montar_preview(): lê o arquivo (CSV determinístico ou PDF via IA),
   devolve as linhas propostas SEM gravar nada, com duplicatas prováveis
   já marcadas — front usa isso pra montar a tabela de revisão editável.
2. confirmar_importacao(): grava em lote (linhas já filtradas/editadas pelo
   usuário na tela de revisão).
3. remover_importacao(): "desfazer importação" — apaga pelo importacao_id.

CSV é parseado sem IA (determinístico, mais barato e mais confiável pra um
formato estruturado). PDF depende de texto extraído (pypdf) + IA
(ai.py:extrair_lancamentos_fatura) — ver aviso de "não testado" lá.
"""

import csv
import io
from datetime import datetime

from db import get_conn, _get_grupo_id
from services.competencia import calcular_competencia
from utils.app_error import AppError


# ---------------------------------------------------------------------------
# CSV — parse determinístico (pura, sem banco — testável de verdade)
# ---------------------------------------------------------------------------

def normalizar_data_importacao(raw: str) -> str | None:
    """Aceita DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, DD/MM/YY. Retorna ISO ou None."""
    raw = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalizar_valor_importacao(raw: str) -> float | None:
    """
    Formato BR ('1.234,56') ou US ('1234.56'). Heurística: presença de
    vírgula decide que ela é o separador decimal (remove pontos de milhar
    antes) — mesma ideia geral do parser do bot (D1), simplificada porque
    aqui o valor já vem isolado numa coluna, sem texto em volta.
    Parênteses ou '-' na frente = valor negativo (estorno/pagamento) —
    quem chama decide se descarta essas linhas.
    """
    raw = (raw or "").strip().replace("R$", "").strip()
    negativo = raw.startswith("-") or raw.startswith("(")
    raw = raw.lstrip("-(").rstrip(")").strip()
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        valor = float(raw)
    except ValueError:
        return None
    return -valor if negativo else valor


_ALIASES_DATA  = ("data", "date")
_ALIASES_DESC  = ("descricao", "descrição", "historico", "histórico", "description")
_ALIASES_VALOR = ("valor", "amount", "value")


def parsear_csv(conteudo: bytes) -> list[dict]:
    """
    Parse determinístico de CSV de fatura: detecta encoding (utf-8 ou
    latin-1 — exports de banco BR costumam vir em latin-1), detecta
    separador (',' ou ';' — conta ocorrências numa amostra) e casa colunas
    por nome (aceita variações comuns em PT/EN).

    Retorna lista de {"data": "YYYY-MM-DD", "descricao": str, "valor": float,
    "categoria_sugerida": None}. Linhas sem data/valor válidos são
    descartadas silenciosamente (rodapé de fatura, linha em branco etc.).
    """
    texto = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = conteudo.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise AppError("Não foi possível ler o arquivo (encoding desconhecido).", 400, "csv_encoding_invalido")

    amostra = texto[:2048]
    separador = ";" if amostra.count(";") > amostra.count(",") else ","

    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)
    if not leitor.fieldnames:
        raise AppError("CSV vazio ou sem cabeçalho.", 400, "csv_vazio")

    colunas = {c.strip().lower(): c for c in leitor.fieldnames}

    def _achar(alternativas):
        for alt in alternativas:
            if alt in colunas:
                return colunas[alt]
        return None

    col_data, col_desc, col_valor = (
        _achar(_ALIASES_DATA), _achar(_ALIASES_DESC), _achar(_ALIASES_VALOR)
    )
    if not (col_data and col_desc and col_valor):
        raise AppError(
            "Não encontrei as colunas de data, descrição e valor no CSV "
            "(cabeçalho esperado: data/descricao/valor ou date/description/amount).",
            400, "csv_colunas_nao_encontradas",
        )

    linhas = []
    for row in leitor:
        data_iso = normalizar_data_importacao(row.get(col_data, ""))
        valor = normalizar_valor_importacao(row.get(col_valor, ""))
        if data_iso is None or valor is None:
            continue
        linhas.append({
            "data": data_iso,
            "descricao": (row.get(col_desc) or "").strip(),
            "valor": valor,
            "categoria_sugerida": None,
        })
    return linhas


# ---------------------------------------------------------------------------
# PDF — texto extraído (pypdf) + IA (ai.py). Não determinístico, ver aviso
# de "não testado contra fatura real" na docstring de
# ai.extrair_lancamentos_fatura.
# ---------------------------------------------------------------------------

def extrair_linhas_pdf(conteudo: bytes) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise AppError("Suporte a PDF não está instalado no servidor.", 500, "pdf_nao_suportado") from exc

    from ai import extrair_lancamentos_fatura

    leitor = PdfReader(io.BytesIO(conteudo))
    texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    if not texto.strip():
        raise AppError(
            "Não consegui ler texto desse PDF — pode ser uma fatura escaneada "
            "(imagem, sem texto selecionável). Tente exportar como CSV.",
            400, "pdf_sem_texto",
        )

    brutos = extrair_lancamentos_fatura(texto)
    linhas = []
    for item in brutos:
        data_iso = normalizar_data_importacao(str(item.get("data", "")))
        valor = item.get("valor")
        if data_iso is None or valor is None:
            continue
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            continue
        linhas.append({
            "data": data_iso,
            "descricao": str(item.get("descricao") or "").strip(),
            "valor": valor,
            "categoria_sugerida": item.get("categoria_sugerida"),
        })
    return linhas


# ---------------------------------------------------------------------------
# Orquestração (banco) — passos 1 e 3 do fluxo
# ---------------------------------------------------------------------------

def _e_pdf(arquivo_nome: str, mimetype: str) -> bool:
    return (mimetype or "").lower() == "application/pdf" or (arquivo_nome or "").lower().endswith(".pdf")


def _marcar_duplicatas(conn, usuario_id: int, gid, linhas: list[dict]) -> None:
    """Mesmo valor + mesma data já lançado (qualquer origem) — não bloqueia
    nada, só sinaliza pra revisão manual decidir (§5.3: 'duplicatas
    prováveis destacadas', não descartadas automaticamente)."""
    with conn.cursor() as cur:
        for linha in linhas:
            if gid:
                cur.execute(
                    "SELECT 1 FROM gastos WHERE grupo_id = %s AND data::date = %s::date "
                    "AND valor = %s LIMIT 1",
                    (gid, linha["data"], linha["valor"]),
                )
            else:
                cur.execute(
                    "SELECT 1 FROM gastos WHERE usuario_id = %s AND grupo_id IS NULL "
                    "AND data::date = %s::date AND valor = %s LIMIT 1",
                    (usuario_id, linha["data"], linha["valor"]),
                )
            linha["duplicata_provavel"] = cur.fetchone() is not None


def montar_preview(usuario_id: int, forma_pagamento_id: int, arquivo_nome: str,
                    conteudo: bytes, mimetype: str) -> dict:
    linhas = extrair_linhas_pdf(conteudo) if _e_pdf(arquivo_nome, mimetype) else parsear_csv(conteudo)

    if not linhas:
        raise AppError("Não encontrei nenhum lançamento nesse arquivo.", 400, "nenhum_lancamento")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        _marcar_duplicatas(conn, usuario_id, gid, linhas)

    return {"arquivo_nome": arquivo_nome, "forma_pagamento_id": forma_pagamento_id, "linhas": linhas}


def confirmar_importacao(usuario_id: int, forma_pagamento_id: int, arquivo_nome: str,
                          linhas: list[dict]) -> dict:
    """
    `linhas` já vem filtrada pelo front (só o que ficou marcado como
    "incluir" na revisão) e com `categoria_id` resolvido (usuário
    escolheu/confirmou a categoria sugerida na tela) — este service não
    faz mais nenhuma triagem, só grava.
    """
    if not linhas:
        raise AppError("Nenhum lançamento selecionado para importar.", 400, "nenhum_lancamento")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dia_fechamento FROM formas_pagamento WHERE id = %s", (forma_pagamento_id,)
            )
            forma_row = cur.fetchone()
            dia_fechamento = forma_row["dia_fechamento"] if forma_row else None

            cur.execute(
                """INSERT INTO importacoes
                       (grupo_id, usuario_id, forma_pagamento_id, arquivo_nome, linhas)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (gid, usuario_id, forma_pagamento_id, arquivo_nome, len(linhas)),
            )
            importacao = dict(cur.fetchone())

            for linha in linhas:
                data_transacao = datetime.strptime(linha["data"], "%Y-%m-%d").date()
                # Mesma regra de competência de qualquer outro gasto no cartão
                # (services/competencia.py) — compra perto do fechamento cai
                # no mês seguinte, não importa se entrou pelo bot, pela web ou
                # por importação de fatura.
                competencia = calcular_competencia(data_transacao, dia_fechamento)
                cur.execute(
                    """INSERT INTO gastos
                           (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                            grupo_id, data, competencia, importacao_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (usuario_id, forma_pagamento_id, linha.get("categoria_id"), linha["valor"],
                     linha.get("descricao", ""), gid, data_transacao, competencia, importacao["id"]),
                )
            conn.commit()
            return importacao


def remover_importacao(usuario_id: int, importacao_id: int) -> bool:
    """Desfazer importação (§5.3): apaga os gastos ligados + o registro da
    importação. Só a própria pessoa/grupo dono pode desfazer (isolamento
    multi-tenant, mesma checagem de todo o resto da API)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT id FROM importacoes WHERE id = %s AND grupo_id = %s", (importacao_id, gid)
                )
            else:
                cur.execute(
                    "SELECT id FROM importacoes WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                    (importacao_id, usuario_id),
                )
            if not cur.fetchone():
                return False
            cur.execute("DELETE FROM gastos WHERE importacao_id = %s", (importacao_id,))
            cur.execute("DELETE FROM importacoes WHERE id = %s", (importacao_id,))
            conn.commit()
            return True
