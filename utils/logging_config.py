"""
utils/logging_config.py — logging estruturado (Fase 7.3 do PLANO_EXECUCAO.md).

Substitui os `print(...)` espalhados pelo código de produção (app.py,
handler.py, services/ai_fallback.py) por um logger de verdade: nível
configurável por ambiente, timestamp, nome do módulo — e principalmente,
sai em STDOUT de um jeito que Railway (ou qualquer plataforma que colete
logs por stdout) consegue filtrar por nível.

NÃO mexe nos `print()` de scripts de linha de comando executados manualmente
(init_db.py, database/migrate.py, reset_db.py, jobs/lancar_fixas.py) — lá
print() é a saída esperada de um comando rodado por uma pessoa no terminal,
não log de servidor de produção; trocar por logger só adicionaria ruído
(prefixo de nível/timestamp) numa saída que já é lida diretamente.
"""

import logging
import os

_CONFIGURADO = False


def configurar_logging() -> None:
    global _CONFIGURADO
    if _CONFIGURADO:
        return

    nivel = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, nivel, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    _CONFIGURADO = True


def obter_logger(nome: str) -> logging.Logger:
    configurar_logging()
    return logging.getLogger(nome)
