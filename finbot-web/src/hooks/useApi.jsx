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

  const refetch = useCallback(() => {
    if (!url || skip) return;
    setLoading(true);
    setErro(null);
    api
      .get(url)
      .then((res) => setDados(res.data))
      .catch((err) => setErro(err))
      .finally(() => setLoading(false));
  }, [url, skip]);

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, skip]);

  return { dados, loading, erro, refetch };
}
