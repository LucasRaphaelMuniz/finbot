import styled from "styled-components";

// Fundo escurecido atrás da gaveta no celular — clicar nele fecha o menu
// (mesmo padrão do Overlay de components/Modal). Só existe abaixo de 860px.
export const Overlay = styled.div`
  display: none;

  @media (max-width: 860px) {
    display: ${({ $aberta }) => ($aberta ? "block" : "none")};
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 90;
  }
`;

// Desktop: coluna fixa (sticky) — a navegação não some quando a página
// rola. Abaixo de 860px vira gaveta deslizante por cima do conteúdo.
export const Nav = styled.nav`
  width: 232px;
  flex-shrink: 0;
  height: 100vh;
  position: sticky;
  top: 0;
  overflow-y: auto;
  background: ${({ theme }) => theme.colors.surface};
  border-right: 1px solid ${({ theme }) => theme.colors.border};
  padding: ${({ theme }) => theme.spacing(5)} ${({ theme }) => theme.spacing(3)};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(5)};

  @media (max-width: 860px) {
    position: fixed;
    inset: 0 auto 0 0;
    width: min(280px, 85vw);
    z-index: 100;
    transform: translateX(${({ $aberta }) => ($aberta ? "0" : "-100%")});
    transition: transform 0.2s ease-out;
  }

  @media (max-width: 860px) and (prefers-reduced-motion: reduce) {
    transition: none;
  }
`;

export const Logo = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(2)};
  font-weight: 700;
  font-size: 17px;
  letter-spacing: -0.01em;
  padding: 0 ${({ theme }) => theme.spacing(2)};
`;

export const LogoMarca = styled.span`
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: ${({ theme }) => theme.colors.primarySolid};
  color: #fff;
  font-size: 16px;
`;

export const Grupo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

export const GrupoTitulo = styled.div`
  font-size: 12px;
  font-weight: 500;
  color: ${({ theme }) => theme.colors.textMuted};
  padding: 0 ${({ theme }) => theme.spacing(2)};
  margin-bottom: ${({ theme }) => theme.spacing(1)};
`;

export const ItemLink = styled.a`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(2.5)};
  min-height: 36px;
  padding: 0 ${({ theme }) => theme.spacing(2)};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme, $ativo }) => ($ativo ? theme.colors.text : theme.colors.textMuted)};
  background: ${({ theme, $ativo }) => ($ativo ? theme.colors.surfaceAlt : "transparent")};
  font-size: 14px;
  font-weight: ${({ $ativo }) => ($ativo ? 600 : 400)};
  text-decoration: none;

  svg {
    flex-shrink: 0;
    color: ${({ theme, $ativo }) => ($ativo ? theme.colors.primary : "currentColor")};
  }

  /* alvo de toque de 44px na gaveta do celular */
  @media (max-width: 860px) {
    min-height: 44px;
  }

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
    color: ${({ theme }) => theme.colors.text};
  }
`;
