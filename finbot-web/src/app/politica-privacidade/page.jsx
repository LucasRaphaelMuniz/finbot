// app/politica-privacidade/page.jsx — Fase 7.5 do PLANO_EXECUCAO.md (LGPD).
// Página pública, fora dos grupos (auth)/(app): não exige login, porque
// precisa estar acessível antes do cadastro (consentimento) e para
// terceiros cujo telefone é cadastrado por outra pessoa (membro de grupo
// que nunca criou conta própria) — ver seção 3 abaixo.
export const metadata = {
  title: "Política de Privacidade — finbot",
};

export default function PoliticaPrivacidadePage() {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "48px 24px", lineHeight: 1.6 }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Política de Privacidade do finbot</h1>
      <p style={{ opacity: 0.7, fontSize: 13, marginBottom: 32 }}>
        Última atualização: {new Date().toLocaleDateString("pt-BR", { year: "numeric", month: "long", day: "numeric" })}
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>1. O que é o finbot</h2>
      <p>
        O finbot é um assistente financeiro operado via WhatsApp e por este site, que
        registra gastos, entradas, despesas fixas e permite acompanhamento de saldo
        individual ou em grupo (ex.: casal, família, república).
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>2. Quais dados coletamos</h2>
      <ul>
        <li>Número de telefone (WhatsApp) e, se você criar conta no site, nome e e-mail.</li>
        <li>Lançamentos financeiros: valores, categorias, formas de pagamento, descrições que você digita ou fotografa (comprovantes) ou fala (áudio).</li>
        <li>Conteúdo de comprovantes (fotos) e áudios enviados ao bot, processados para extrair valor e descrição.</li>
        <li>Dados técnicos mínimos de operação (logs de erro, limite de mensagens por minuto) — não usados para perfilamento ou publicidade.</li>
      </ul>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>3. Dados de terceiros (membros de grupo)</h2>
      <p>
        Se você cadastra outra pessoa como membro do seu grupo (ex.: cônjuge, familiar),
        o telefone dela é armazenado para que o bot reconheça as mensagens enviadas por
        esse número. Essa pessoa pode não ter dado consentimento diretamente ao finbot —
        é responsabilidade de quem cadastra informar o membro e obter sua concordância.
        Qualquer membro pode pedir a remoção do próprio telefone a qualquer momento,
        pelo WhatsApp (comando <code>grupo remover</code>) ou pelo contato indicado na
        seção 8.
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>4. Com quem compartilhamos dados</h2>
      <p>Usamos os seguintes prestadores de serviço para operar o finbot:</p>
      <ul>
        <li><strong>Evolution API</strong> — intermediação das mensagens do WhatsApp.</li>
        <li><strong>OpenAI</strong> — leitura de comprovantes (imagem) e transcrição de áudio, e interpretação de mensagens em texto livre quando nenhum comando é reconhecido.</li>
        <li><strong>Supabase</strong> — banco de dados e autenticação do site.</li>
        <li><strong>Railway</strong> — hospedagem do servidor.</li>
      </ul>
      <p>
        Não vendemos dados a terceiros nem os usamos para publicidade.
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>5. Base legal e finalidade (LGPD)</h2>
      <p>
        Tratamos seus dados para <strong>execução do serviço</strong> que você solicitou
        (registrar e consultar seus gastos) e, no caso de membros de grupo, por
        <strong> legítimo interesse</strong> do responsável pelo grupo em organizar as
        finanças compartilhadas.
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>6. Retenção</h2>
      <p>
        Seus dados ficam armazenados enquanto sua conta existir. Lançamentos que
        pertencem a um grupo (não só a você) são preservados mesmo após sua saída ou
        exclusão de conta, pois também são de interesse legítimo dos demais membros —
        ver seção 7.
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>7. Exclusão de conta — o que acontece de fato</h2>
      <p>
        Ao excluir sua conta pela tela <a href="/conta">Conta</a>, o finbot:
      </p>
      <ul>
        <li>Remove você do grupo (suas formas de pagamento voltam a ser individuais).</li>
        <li>Anonimiza seu nome e telefone no nosso banco de dados.</li>
        <li>
          <strong>Não apaga</strong> gastos/entradas já lançados enquanto você estava no
          grupo — eles ficam vinculados ao grupo (não mais ao seu usuário) porque também
          são dado financeiro de interesse dos outros membros. Apagá-los quebraria o
          histórico financeiro de terceiros.
        </li>
      </ul>
      <p>
        <strong>Limitação importante:</strong> a exclusão descrita acima não remove seu
        login (Supabase Auth) automaticamente — isso exige uma ação manual da nossa
        parte. Se você quiser que seu login também seja apagado, entre em contato pelo
        e-mail da seção 8 após excluir a conta pelo site.
      </p>

      <h2 style={{ fontSize: 18, marginTop: 32 }}>8. Seus direitos e contato</h2>
      <p>
        Você pode pedir acesso, correção, portabilidade ou exclusão dos seus dados, ou
        tirar dúvidas sobre este documento, escrevendo para{" "}
        <a href="mailto:hitlucas1@gmail.com">hitlucas1@gmail.com</a>.
      </p>
    </div>
  );
}
