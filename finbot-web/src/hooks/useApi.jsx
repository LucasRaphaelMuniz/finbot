"use client";

// hooks/useApi.jsx — wrapper fino sobre services/api.js com os 3 estados
// que toda tela de dado precisa (loading/erro/dado), pra não repetir esse
// boilerplate em cada page.jsx. Uso:
//   const { dados, loading, erro, refetch } = useApi("/gastos?mes=2026-07");
import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/services/api";

export function useApi(url, { skip = false } = {}) {
  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [erro, setErro] = useState(null);

  // Numera cada chamada de refetch. Sem isso, 2 refetch() disparados perto
  // um do outro (ex: arrastar 2 cards em sequência em /contas — cada
  // drag chama refetch({silent:true}) no fim) correm risco de resolver
  // FORA de ordem por variação de rede: a resposta do 1º pode chegar
  // DEPOIS da do 2º e sobrescrever `dados` com um estado mais velho — o
  // card recém-movido pisca de volta pro lugar antigo por um instante
  // ("buga e volta", reportado pelo Lucas em 24/07/2026). Guardando o id
  // da chamada mais recente, uma resposta só é aplicada se ninguém mais
  // novo foi disparado nesse meio-tempo; a resposta desatualizada é
  // descartada, sabendo que a mais nova (ou já aplicada, ou a caminho) tem
  // o dado certo.
  const idRef = useRef(0);

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
    const id = ++idRef.current;
    api
      .get(url)
      .then((res) => {
        if (id === idRef.current) setDados(res.data);
      })
      .catch((err) => {
        if (id === idRef.current) setErro(err);
      })
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
