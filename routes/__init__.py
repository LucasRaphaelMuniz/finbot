"""
routes/__init__.py — agrega e registra todos os Blueprints da API web
(Fase 4.3 do PLANO_EXECUCAO.md). app.py só chama register_routes(app);
nenhuma lógica de negócio aqui, só a lista de módulos.
"""

from routes import onboarding, convites, gastos, entradas, fixas, categorias, formas, grupo, resumo, importacao, planos, conta, verificacao

_BLUEPRINTS = [
    onboarding.bp,
    convites.bp,
    gastos.bp,
    entradas.bp,
    fixas.bp,
    categorias.bp,
    formas.bp,
    grupo.bp,
    resumo.bp,
    importacao.bp,
    planos.bp,
    conta.bp,
    verificacao.bp,
]


def register_routes(app):
    for bp in _BLUEPRINTS:
        app.register_blueprint(bp)
