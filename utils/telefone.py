"""
utils/telefone.py — normalização única de telefone/JID do WhatsApp.

Antes desta consolidação (Fase A do AUDITORIA_E_PLANO_CADASTRO.md, F1), a
mesma lógica existia duplicada e DIVERGENTE em dois lugares:
- app.py:_normalizar_jid — usada no webhook, já tinha a correção do 9º
  dígito (celular BR ganhou um dígito extra em 2016) e filtrava JIDs de
  grupo (@g.us) e dispositivo linkado (@lid).
- handler.py:_normalizar_telefone — usada nos comandos do bot (`vincular`,
  `grupo add`), NÃO tinha a correção do 9º dígito.

A divergência não era só duplicação de código: era a causa raiz do F1 (bug
crítico da auditoria) — a API web nunca normalizava telefone nenhum, salvava
cru ('44912345678'), enquanto o bot salvava sempre como JID
('5544912345678@s.whatsapp.net'). Qualquer SELECT que tentasse achar "esse
telefone já existe?" comparava strings em formatos diferentes e nunca
batia, criando usuário duplicado toda vez que a mesma pessoa usava bot E
web.

Esta é agora a ÚNICA função de normalização do projeto — app.py e
handler.py importam daqui em vez de manter cópias próprias (Fase A3).
"""

import re

_JID_SUFFIX = "@s.whatsapp.net"


def normalizar(telefone: str | None) -> str | None:
    """
    Converte qualquer formato de telefone brasileiro (ou um JID já pronto)
    para o formato canônico de armazenamento: '5544912345678@s.whatsapp.net'.

    Aceita: '44912345678', '5544912345678', '+55 (44) 91234-5678',
    '44 91234-5678', ou um JID já pronto ('...@s.whatsapp.net').
    Retorna None para entrada vazia, inválida, ou JID de grupo (@g.us) /
    dispositivo linkado (@lid) — essas não representam uma pessoa.
    """
    if not telefone:
        return None
    telefone = telefone.strip()

    if "@g.us" in telefone or "@lid" in telefone:
        return None

    telefone = re.sub(r"^whatsapp:\+?", "", telefone)

    if _JID_SUFFIX in telefone:
        digits = telefone.split("@")[0]
    else:
        digits = re.sub(r"\D", "", telefone)

    if not digits:
        return None

    # 10-11 dígitos = DDD + número, sem código do país -> assume Brasil (55)
    if len(digits) in (10, 11):
        digits = "55" + digits

    # Formato antigo (55 + DDD + 8 dígitos, sem o 9º dígito do celular,
    # adicionado em 2016): insere o 9 extra quando o número local já começa
    # com 9 (padrão de celular). Antes só existia em app.py:_normalizar_jid
    # — agora aplicada em QUALQUER ponto de entrada (bot ou web), o que
    # antes não acontecia em handler.py e era parte do F1.
    if len(digits) == 12 and digits.startswith("55"):
        local = digits[4:]  # 8 dígitos locais
        if local.startswith("9"):
            digits = digits[:4] + "9" + local

    if len(digits) not in (12, 13):
        return None

    return digits + _JID_SUFFIX


def exibir(telefone_ou_jid: str | None) -> str:
    """
    Formata um telefone/JID para exibição amigável: '+55 44 91234-5678'.

    Aceita entrada já normalizada (JID) ou crua (chama normalizar() antes).
    Nunca lança exceção — se não conseguir formatar, devolve a entrada
    original (ou string vazia); é usada direto em telas, um erro aqui não
    pode quebrar a renderização.
    """
    if not telefone_ou_jid:
        return ""
    jid = telefone_ou_jid if _JID_SUFFIX in telefone_ou_jid else normalizar(telefone_ou_jid)
    if not jid:
        return telefone_ou_jid

    digits = jid.replace(_JID_SUFFIX, "")
    if len(digits) == 13:  # 55 + DDD(2) + 9 dígitos
        pais, ddd, numero = digits[:2], digits[2:4], digits[4:]
        return f"+{pais} {ddd} {numero[:5]}-{numero[5:]}"
    if len(digits) == 12:  # 55 + DDD(2) + 8 dígitos
        pais, ddd, numero = digits[:2], digits[2:4], digits[4:]
        return f"+{pais} {ddd} {numero[:4]}-{numero[4:]}"
    return "+" + digits
