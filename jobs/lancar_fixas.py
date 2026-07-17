"""
jobs/lancar_fixas.py — lança as despesas fixas do dia como gastos normais.

Atualização de 16/07/2026: o caminho automático principal não é mais um
Cron Job separado do Railway (decisão D4 original) — é uma thread dentro do
próprio processo web (`app.py::_loop_lancar_fixas_diario`), pra não exigir
um segundo serviço no Railway. Ver o comentário em app.py pra entender o
trade-off assumido (múltiplos workers gunicorn todos tentando lançar, idem­
potência garantida pelo índice único uq_despesa_fixa_mes).

Este script continua útil pra:
- Rodar manualmente em dev/teste: `python -m jobs.lancar_fixas`.
- Catch-up manual pontual em produção, se por algum motivo a thread não
  rodou (ex: reiniciar o processo várias vezes no mesmo dia) — dá pra
  disparar via shell do Railway sem precisar configurar um Cron Job.
- Voltar a ser um Cron Job de verdade no futuro, se downtime do processo
  web virar um problema recorrente (nesse caso a thread para de rodar
  junto) — o código já está pronto pra isso, só precisa criar o serviço.
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
