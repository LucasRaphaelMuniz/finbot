"""
utils/app_error.py — exceção customizada para a API web (Fase 4.3 do
PLANO_EXECUCAO.md, padrão CLAUDE.md: services/routes dão `raise AppError(...)`
em vez de cada view function montar `return jsonify(erro), status` na mão.
Um único errorhandler central em app.py converte isso em resposta HTTP.

Contrato de resposta (consumido pelo finbot-web):
    {"erro": "<codigo_curto>", "mensagem": "<texto humano>"}
`erro` é uma chave estável pro front tratar casos específicos por código
(ex: "sem_grupo" — ver (app)/layout.jsx no finbot-web). `mensagem` é o texto
pra mostrar na tela; nunca o contrário (front nunca deve exibir `erro` cru
pro usuário, nem comparar `mensagem` para decidir fluxo).
"""


class AppError(Exception):
    def __init__(self, mensagem: str, status_code: int = 400, codigo: str = "erro_generico"):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status_code = status_code
        self.codigo = codigo

    def to_dict(self) -> dict:
        return {"erro": self.codigo, "mensagem": self.mensagem}
