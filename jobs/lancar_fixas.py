"""
jobs/lancar_fixas.py — job diário (cron do Railway, decisão D4 do
PLANO_EXECUCAO.md) que lança as despesas fixas do dia como gastos normais.

Uso:
    python -m jobs.lancar_fixas

Railway: configurar como Cron Job separado do processo web (não dentro do
gunicorn), rodando 1x/dia. Um cron sobrevive a deploy e não corre risco de
lançar em duplicidade com múltiplos workers gunicorn — ao contrário de um
scheduler in-process tipo APScheduler dentro do processo web (D4).
"""

from services.despesas_fixas import lancar_despesas_fixas_do_mes


def main():
    lancados = lancar_despesas_fixas_do_mes()
    if not lancados:
        print("→ Nenhuma despesa fixa a lançar hoje.")
        return
    print(f"✅ {len(lancados)} despesa(s) fixa(s) lançada(s):")
    for gasto in lancados:
        print(f"   • gasto id={gasto['id']} valor={gasto['valor']} descricao={gasto['descricao']}")


if __name__ == "__main__":
    main()
