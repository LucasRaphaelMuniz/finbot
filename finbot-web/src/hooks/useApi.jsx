"use client";

// hooks/useApi.jsx — wrapper fino sobre services/api.js com os 3 estados
// que toda tela de dado precisa (loading/erro/dado), pra não repetir esse
// boilerplate em cada page.jsx. Uso:
//   const { dados, loading, erro, refetch } = useApi("/gastos?mes=2026-07");
import { useCallback, useEffect, useState } from "react";
import api from "@/services/api";

export function useApi(url, { skip = false } = {}) {
  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [erro, setErro] = useState(null);

  // `refetch({ silent: true })` — pedido do Lucas em /contas: arrastar um
  // card chamava refetch() puro, que liga `loading`, e a tela troca o board
  // inteiro pelo <Loading/> a cada solta. Com silent, os dados são
  // atualizados por baixo sem esse takeover — a tela troca só o que mudou
  // de verdade. Default sem silent continua igual (outras telas que chamam
  // refetch() depois de salvar um modal não precisam mudar nada).
  const refetch = useCallback(({ silent = false } = {}) => {
    if (!url || skip) return;
    if (!silent) setLoading(true);
    setErro(null);
    api
      .get(url)
      .then((res) => setDados(res.data))
      .catch((err) => setErro(err))
      .finally(() => {
        if (!silent) setLoading(false);
      });
  }, [url, skip]);

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, skip]);

  return { dados, loading, erro, refetch };
}
