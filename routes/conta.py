"""routes/conta.py — DELETE /api/conta (Fase 5.6, reescrita na Fase 7.5 /
LGPD, senha validada server-side na Fase D1). Sem @requer_grupo de
propósito: contas individuais (sem grupo, ver services/conta.py) também
precisam poder se excluir — @requer_grupo bloquearia esse caso com 404
"sem_grupo" antes mesmo de chegar aqui."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated
from services.conta import excluir_conta, get_meu_status, marcar_tutori