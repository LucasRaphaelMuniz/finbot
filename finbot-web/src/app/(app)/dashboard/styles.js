import styled, { css, keyframes } from "styled-components";

// Estilos do Início (redesign de 05/11/2026). Um nível de superfície só:
// blocos em `surface` sobre o `bg` da página, sem card dentro de card.

const tomCor = ({ theme, $tom }) =>
  $tom === "perigo" ? theme.colors.danger
    : $tom === "alerta" ? theme.colors.warning
      : $tom === "entrada" ? theme.colors.success
        : theme.colors.text;

export const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const Titulo = styled.h1`
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
`;

const blocoBase = css`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(5)};

  @media (max-width: 640px) {
    padding: ${({ theme }) => theme.spacing(4)};
  }
`;

// ---- 1. número principal ---------------------------------------------------

export const Hero = styled.section`
  ${blocoBase}
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const HeroRotulo = styled.div`
  font-size: 14px;
  color: ${({ theme }) => theme.colors.textMuted};
`;

export const HeroValor = styled.div`
  font-size: clamp(30px, 6vw, 40px);
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
  margin-top: ${({ theme }) => theme.spacing(1)};
  color: ${({ theme, $negativo }) => ($negativo ? theme.colors.danger : theme.colors.text)};
`;

export const HeroBarra = styled.div`
  height: 8px;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  overflow: hidden;
  margin-top: ${({ theme }) => theme.spacing(4)};
`;

export const HeroBarraCheia = styled.div`
  height: 100%;
  border-radius: 999px;
  background: ${({ theme, $tom }) =>
    $tom === "perigo" ? theme.colors.danger : $tom === "alerta" ? theme.colors.warning : theme.colors.primary};
`;

export const HeroLegenda = styled.div`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: ${({ theme }) => theme.spacing(2)};
`;

export const Chips = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr));
  gap: ${({ theme }) => theme.spacing(3)};
  margin-top: ${({ theme }) => theme.spacing(5)};
  padding-top: ${({ theme }) => theme.spacing(4)};
  border-top: 1px solid ${({ theme }) => theme.colors.border};

  @media (max-width: 480px) {
    grid-template-columns: 1fr 1fr;
  }
`;

export const Chip = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;

  span {
    font-size: 13px;
    color: ${({ theme }) => theme.colors.textMuted};
  }

  strong {
    font-size: 16px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: ${tomCor};
  }

  small {
    font-size: 12px;
    color: ${({ theme }) => theme.colors.textMuted};
  }
`;

// ---- blocos -------------------------------------------------------------------

export const Grade = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(340px, 100%), 1fr));
  gap: ${({ theme }) => theme.spacing(5)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const Bloco = styled.section`
  ${blocoBase}
  min-width: 0;
`;

export const BlocoTopo = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(3)};
`;

export const BlocoTitulo = styled.h2`
  font-size: 16px;
  font-weight: 600;
`;

export const LinkVerTodos = styled.a`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: ${({ theme }) => theme.colors.primary};
  text-decoration: none;
  white-space: nowrap;
  min-height: 32px;

  &:hover {
    text-decoration: underline;
  }
`;

export const Valor = styled.span`
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  white-space: nowrap;
  color: ${tomCor};
`;

export const Vazio = styled.p`
  font-size: 14px;
  color: ${({ theme }) => theme.colors.textMuted};
  padding: ${({ theme }) => theme.spacing(4)} 0;
`;

export const TudoPago = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(3)} 0;
  font-size: 14px;
  font-weight: 500;

  svg {
    color: ${({ theme }) => theme.colors.success};
    flex-shrink: 0;
  }

  small {
    display: block;
    font-size: 12px;
    font-weight: 400;
    color: ${({ theme }) => theme.colors.textMuted};
    font-variant-numeric: tabular-nums;
  }
`;

// ---- 2. a vencer -------------------------------------------------------------

export const LinhaConta = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(2.5)} 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-size: 14px;

  &:last-of-type {
    border-bottom: none;
  }
`;

export const ContaNome = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
`;

export const ContaPrazo = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: ${({ $tom }) => ($tom === "neutro" ? 400 : 600)};
  color: ${({ theme, $tom }) =>
    $tom === "perigo" ? theme.colors.danger : $tom === "alerta" ? theme.colors.warning : theme.colors.textMuted};
`;

// ---- 3. onde foi o dinheiro -----------------------------------------------------

export const CatLinha = styled.li`
  display: grid;
  grid-template-columns: minmax(80px, 30%) minmax(0, 1fr) auto;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(2)} 0;
  font-size: 14px;
`;

export const CatNome = styled.span`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const CatTrilho = styled.div`
  height: 8px;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  overflow: hidden;
`;

export const CatBarra = styled.div`
  height: 100%;
  border-radius: 999px;
`;

export const CatValor = styled.span`
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  white-space: nowrap;
  text-align: right;

  small {
    display: inline-block;
    min-width: 36px;
    margin-left: 6px;
    font-size: 12px;
    font-weight: 400;
    color: ${({ theme }) => theme.colors.textMuted};
  }
`;

export const Divisao = styled.div`
  margin-top: ${({ theme }) => theme.spacing(4)};
  padding-top: ${({ theme }) => theme.spacing(4)};
  border-top: 1px solid ${({ theme }) => theme.colors.border};
`;

export const DivisaoBarra = styled.div`
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: ${({ theme }) => theme.colors.textMuted};

  span {
    background: ${({ theme }) => theme.colors.primary};
  }
`;

export const DivisaoLegenda = styled.div`
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(2)};
  margin-top: ${({ theme }) => theme.spacing(2)};
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  font-variant-numeric: tabular-nums;

  i {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
    background: ${({ theme }) => theme.colors.textMuted};
  }

  i[data-tipo="fixo"] {
    background: ${({ theme }) => theme.colors.primary};
  }
`;

// ---- 4. últimos lançamentos -------------------------------------------------------

export const Dia = styled.div`
  & + & {
    margin-top: ${({ theme }) => theme.spacing(2)};
  }
`;

export const DiaTopo = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.textMuted};
  font-variant-numeric: tabular-nums;
  padding: ${({ theme }) => theme.spacing(2)} 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`;

export const Lancamento = styled.li`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(3)} 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};

  &:last-child {
    border-bottom: none;
  }
`;

export const Avatar = styled.span`
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
`;

export const LancTexto = styled.div`
  flex: 1;
  min-width: 0;
`;

export const LancTitulo = styled.div`
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const LancMeta = styled.div`
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textMuted};
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
`;

// ---- 5. gráfico ------------------------------------------------------------------

export const ChartCard = styled.section`
  ${blocoBase}
`;

export const ChartTitulo = styled.h2`
  font-size: 16px;
  font-weight: 600;
  margin-bottom: ${({ theme }) => theme.spacing(3)};
`;

// ---- carregando -------------------------------------------------------------------

const pulsar = keyframes`
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
`;

export const SkeletonLinha = styled.div`
  height: 14px;
  border-radius: 6px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  animation: ${pulsar} 1.4s ease-in-out infinite;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
`;

// Popup de detalhe ao clicar numa barra do gráfico "últimos 6 meses"
// (pedido do Lucas, 24/07/2026). Mesmo desenho de components/Modal + lista
// usado em (app)/contas/styles.js pro detalhe de fatura — duplicado aqui
// (poucas linhas) em vez de compartilhado entre páginas, mesmo padrão já
// usado no projeto de cada tela ter seu styles.js próprio.
export const ListaDetalhe = styled.div`
  min-width: 320px;
  max-width: 420px;
  max-height: 50vh;
  overflow-y: auto;
`;

export const ItemDetalhe = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(2)} 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-size: 14px;

  &:last-child {
    border-bottom: none;
  }
`;

export const TextoMuted = styled.div`
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: 2px;
`;

// Linha clicável de forma de pagamento (24/07/2026, pedido do Lucas: "abre
// primeiro pela forma de pagamento, clicar expande o detalhamento"). Usa
// <button> de propósito (não div+onClick) — foco por teclado e semântica
// de "isto é acionável" de graça.
export const GrupoForma = styled.button`
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(3)} 0;
  border: none;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  background: none;
  color: ${({ theme }) => theme.colors.text};
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }
`;

// Item dentro de um grupo expandido — mesmo desenho de ItemDetalhe, só
// recuado e sem borda própria (a borda de baixo do grupo/último item já
// separa visualmente do próximo grupo).
export const ItemAninhado = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(2)} 0 ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(5)};
  font-size: 13px;

  &:last-child {
    border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  }
`;
