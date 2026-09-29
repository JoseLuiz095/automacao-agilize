## 0.9.11

- Fallback seguro para NFS-e pré-cadastrada com prefixo indevido no número, como `2721` x `2600000002721`.
- Busca de contingência da nota atual por CNPJ/nome do fornecedor inclui o mês da emissão + 3 meses anteriores.
- Reutilização exige conferência de empresa, fornecedor, valor e emissão antes de aceitar o número por sufixo.
- Publicador passa a inicializar Git quando o projeto veio de ZIP, alinhar o novo commit sobre `origin/main` e preservar o histórico remoto.
- `07_PUBLICAR_VERSAO.bat` passa a interromper a publicação se o push do código-fonte falhar.

## 0.9.10

- Pesquisa do Agilize ganhou espera de estabilização da grade antes da leitura dos resultados.
- Debounce de pesquisa ficou ligeiramente mais conservador sem desacelerar o preenchimento normal do formulário.
- Mantida a janela de três meses completos anteriores para histórico NFS-e.

## 0.9.9

- NFS-E: histórico ampliado para 3 meses completos anteriores ao mês da nota atual.
- NFS-E: confirmação visual/reaplicação dos filtros de data após rerender do Livewire.
- Cache histórico alinhado à nova janela de pesquisa.

## 0.9.8
- Registros Aguardando Aprovacao/Efetuada deixam de ser reprocessados.
- Melhor fallback para acoes Editar/Ver nota.
- Campo Anexo opcional em registros existentes quando o Agilize nao o expoe.
- Pre-check de registro atual antes da pesquisa historica e cache de historico.
- Removida a aba E-mail / Downloads.
- Reduzidos reloads e esperas redundantes.

# Changelog

## 0.9.7

- ampliado o painel **Ver detalhes** para facilitar lotes com muitos lançamentos;
- adicionado botão **Copiar detalhes** para copiar o log completo para a área de transferência;
- adicionado botão **Limpar detalhes**;
- adicionada barra de rolagem fina no painel de log.

## 0.9.6

- Fila alterada para processamento sequencial: 1 lançamento por vez.
- Aviso visual antes de processar lotes com múltiplos lançamentos.
- Próximo lançamento é liberado automaticamente após enviar/cancelar/fechar o atual.
- Botão principal atualizado para `PREPARAR TODOS (1 POR VEZ)`.
- Mantida a recuperação para `ERR_INSUFFICIENT_RESOURCES` como proteção adicional.

## 0.9.5
- Corrige esgotamento de recursos do Chromium em lotes grandes com limite seguro de workspaces e retomada automática da fila.
- Adiciona retry específico para `ERR_INSUFFICIENT_RESOURCES`.
- Adiciona aba E-mail / Downloads com busca Zimbra via IMAP por remetente e período.
- Anexos PDF podem entrar automaticamente na fila.
- Links de portal NFS-e/hCaptcha ficam pendentes para abertura e download manual.

## 0.9.4

- Mesmo Número da nota passa a reutilizar qualquer registro existente, independentemente da Situação de Entrada.
- Pesquisa da nota atual passa a usar Todos os status.
- Busca anti-duplicidade possui tentativas com mês atual, período ampliado e todas as empresas.
- Empresa, fornecedor, valor e emissão viram critérios de preferência, não motivos para criar outra nota.
- Se a nota existe mas não for possível abrir Editar/Ver nota, o lançamento novo é bloqueado por segurança.

## 0.9.3

- Corrigido pareamento do recibo/boleto Auditor 2894 com o DANFSe oficial.
- Nova filial LCR 0029-40 reconhecida como empresa/tomador.
- Pré-lançamentos NFS-E em `Não possui` são procurados antes da criação de uma nova nota.
- Resolução dinâmica de empresa pelo select do Agilize para filiais novas.

## 0.9.2
- Em `Doc. - Contas a pagar`, amplia a janela histórica para hoje menos 2 meses até hoje.
- Datas são aplicadas imediatamente antes da busca pelo fornecedor, depois dos demais filtros.
- Aguarda debounce do Livewire e confirma/reaplica os campos de data quando necessário.
- Mantém a pesquisa de Contas a pagar pelo nome do fornecedor.

# 0.9.1

- Doc. - Contas a pagar passa a pesquisar o histórico exclusivamente pelo nome do fornecedor.
- Destino do lançamento resolvido antes da pesquisa histórica.
- Modo Automático da LOL não visita NFS-E para procurar observação.
- Recuperação automática de `Target page, context or browser has been closed`, com uma repetição segura do grupo.
- Sessão fechada deixa de contaminar os lançamentos seguintes da fila.

## 0.9.0

- Em `Doc. - Contas a pagar`, a pesquisa histórica usa o nome do fornecedor/beneficiário em vez do número da nota/fatura.
- Mantida a pesquisa por CNPJ em `Notas NFS-E`.
- Logs passam a informar explicitamente o nome usado na pesquisa histórica.

## 0.8.9


- separa a area de destino do lancamento da area usada para pesquisa historica;
- `Doc. - Contas a pagar` selecionado passa a ser respeitado como destino final;
- modo Automatico direciona Nota de Debito/LOL para `Doc. - Contas a pagar`;
- historico pode ser reaproveitado de NFS-E sem redirecionar o lancamento atual para NFS-E;
- adiciona protecao para nunca criar NFS-E como fallback quando o destino correto e `/documentos`.

## 0.8.5

- compatibilidade com a atualização do Agilize que passou a abrir notas por `openNfsModal(id)`;
- busca da nota-base aceita `Editar` como botão/link e `Ver nota`;
- leitura da observação passa a usar o estado Livewire `serverMemo.data.nfs.description` como fonte principal;
- espera correta da segunda etapa do modal Livewire antes de copiar observação/aprovador;
- mantém fallback pelo textarea para compatibilidade com layouts anteriores.

# Changelog

## 0.8.4

- Pareamento Starting Hub: NFS-e 2657 + boleto Sicoob pelo N. documento 2657.
- Demonstrativos explicitamente sem valor fiscal deixam de criar lançamento e não são anexados.
- Validação de dígitos do CNPJ para evitar falso positivo em linha digitável/código de barras.
- Correção do layout de NFS-e da Prefeitura de Linhares para número fiscal e RPS.
- Correções de CNPJ/nome do fornecedor, valor, vencimento, Nosso Número e referência mensal em boletos Sicoob.

## 0.8.3

- remove dependência de GitHub Actions no atualizador;
- remove comparação com `VERSAO.txt` para usuários finais;
- usa apenas a última GitHub Release como fonte oficial;
- remove o estado “Aguardar instalador”;
- publica Setup + SHA localmente pelo `07_PUBLICAR_VERSAO.bat`;
- Release incompleta passa a ser erro de publicação, não estado de espera.

## v0.8.2

- Observação do mês anterior passa a ser copiada integralmente, em vez de reutilizar somente o RATEIO.
- Atualização conservadora de dados reconhecidos nos PDFs: vencimento, meio de pagamento/banco, referência mensal, número do documento, nosso número, valor do documento e número fiscal quando houver rótulo explícito.
- Textos livres e instruções operacionais, como `(Obter no DDA)`, são preservados.
- Datas presentes em rateio ou texto livre não são alteradas; somente linhas de vencimento/pagamento são atualizadas.
- Parser FINNET passa a extrair `Meio de Pagamento`, `Ref. mês/ano`, Fatura e Nosso Número com maior precisão.
- Regressão v0.8.2 adicionada para o cenário FINNET.

## v0.8.1

- workflow passa a criar Release automaticamente ao alterar `VERSAO.txt` em `main`;
- removida dependência de criação manual de tag para publicar o instalador;
- novo botão `Aguardar instalador` durante o build do GitHub Actions;
- updater passa a comparar Release e `VERSAO.txt`, evitando que uma Release antiga esconda código novo;
- suporte a credencial já existente no Git Credential Manager para repositório privado do desenvolvedor;
- validação de projeto passa a executar automaticamente todos os `test_regressoes_v*.py`;
- regressão específica para o caso v0.7.3 instalada + v0.8.x em publicação.

# v0.8.0

- Novo motor de pareamento por evidências documentais.
- NFS-e/recibo: pareamento por número fiscal.
- Nota de débito/boletos LOL: pareamento Fatura x Nº do Documento.
- SKYTEF: pareamento RPS x Nº do Documento com sufixo de parcela, ex. 991483 x 991483-01.
- Bloqueio de pareamento quando CNPJ do fornecedor, empresa ou valor divergem.
- Correção da leitura do Número da Nota em layouts da Prefeitura de São Paulo.
- Correção do valor fiscal em NFS-e com IBS/CBS.
- Correção do valor do boleto em layouts que extraem rótulos e valores fora de ordem.
- Novos aliases de pagador para Jaguaré e Santa Teresa.
- Regressão v0.8.0 adicionada ao validador do projeto.

# v0.7.4

- Corrigido pareamento FINNET: boleto usa o campo `NOTA FISCAL` como referência principal.
- `02343301` passa a ser relacionado à nota `47736`; `02343401` à nota `47737`.
- Campo `FATURA` do boleto passa a ser extraído como referência secundária.
- Corrigida leitura de `VALOR A PAGAR`, incluindo cobranças com múltiplos itens.
- Notas fiscais de serviço de Barueri passam a ser classificadas como NFS-E, mesmo quando o documento usa a sigla `NFE`.
- Adicionado teste de regressão específico para FINNET.

# v0.7.3

- Suporte a notas de debito/boletos de internet e pareamento por fatura.
- Pesquisa historica sem NF-e/CT-e.
- Ambiente TESTE via BAT apontando para dev-ml.startinghub.com.br.

# v0.7.1

- GitHub Release passou a ser a fonte oficial do atualizador.
- VERSAO.txt passou a ser apenas fallback/diagnostico.
- HTTP 404 do repositorio nao aparece mais como erro da aplicacao.
- Estados offline, rate-limit e Release em preparacao receberam feedback neutro.
- Banner principal aparece apenas para atualizacao instalavel.
- Atualizacao exige Setup.exe + SHA-256.
- Ferramentas de GitHub e diagnostico foram reforcadas.
- Corrigido FERRAMENTAS/02_VALIDAR_PROJETO.bat, que ainda apontava para teste antigo inexistente.

# Changelog

## 0.7.0

- fila em massa para 1 ou mais PDFs;
- agrupamento independente da ordem pelo Nº NFS-e;
- associação nota + boleto e suporte a documento único;
- preparação de vários formulários sem esperar o envio manual do anterior;
- pesquisa de histórico com fallback entre NF-e/CT-e, NFS-E e Contas a pagar;
- interface com seleção das áreas equivalentes ao menu do Agilize;
- arquitetura separada para novos adaptadores de tipos de lançamento.

## 0.6.2

- corrigido o fluxo de documento único: com 1 PDF o botão de processamento é habilitado;
- adicionado aviso visual persistente quando apenas 1 PDF está anexado;
- antes de processar 1 PDF, o sistema confirma com o usuário que deseja continuar;
- tela de Atualizações redesenhada no padrão funcional usado como referência no Monitor Carat + PDV;
- verificação automática agora deixa um aviso visível na tela principal quando existe versão nova;
- quando há uma Release instalável, o aplicativo oferece atualização logo após iniciar;
- atualizador consulta a Release e também o `VERSAO.txt` do GitHub;
- se o código estiver em uma versão mais nova mas o Setup.exe ainda não tiver sido publicado, o sistema informa isso sem aparentar falha;
- adicionado log de atualização em `%LOCALAPPDATA%\AutomacaoAgilize\logs\update.log`;
- adicionados testes de regressão para documento único e cenários do atualizador.

## 0.6.1

- corrigido o caminho raiz usado pelo `AutomacaoAgilize.spec`;
- o PyInstaller agora resolve corretamente `app/launcher.py` a partir da pasta `build`;
- adicionada validação prévia de `launcher.py`, `.spec` e ícone antes do build;
- o log do instalador registra `ROOT`, `SPEC` e `LAUNCHER` para facilitar diagnóstico;
- build local e GitHub Actions passam a usar a mesma resolução de caminhos.

## 0.6.0

- projeto reorganizado em `app`, `assets`, `build`, `installer`, `FERRAMENTAS`, `DOCUMENTACAO` e `tests`;
- dados persistentes separados do código instalado;
- ícone próprio no EXE, janela, atalhos, instalador e barra de tarefas;
- `AppUserModelID` fixo e instância única;
- scrollbar personalizada, fina e sem setas;
- interface principal mais compacta e responsiva;
- suporte a adicionar os PDFs em etapas e remover arquivo individualmente;
- atualização com SHA-256 quando publicado pela Release;
- atualização executada após o fechamento do aplicativo, evitando conflito com o instalador;
- ambiente de build movido para `%LOCALAPPDATA%`;
- geração local e GitHub Actions alinhados ao mesmo `VERSAO.txt`.
## 0.7.3
- Corrigida a deteccao incorreta de repositorio ausente quando apenas nao havia Release.
- Adicionada consulta separada aos metadados do repositorio.
- `VERSAO.txt` agora e lido pela GitHub Contents API na branch padrao real.
- Adicionado suporte opcional a repositorio privado via token de ambiente.
- Adicionado fallback de desenvolvimento por Git/Git Credential Manager.
- Download autenticado de assets privados suportado quando token esta configurado.
- Nova regressao cobrindo 404 de Release com repositorio existente.

## 0.8.6
- Corrige pesquisa da nota-base para considerar somente **Situação de Entrada = Efetuada**.
- Rejeita em código registros `Não possui`, `Aguardando Entrada` etc., mesmo se o filtro do Livewire não permanecer aplicado.
- Reforça validação de empresa/filial na escolha do histórico.

## 0.8.7
- Corrigida leitura da Observacao no modal Livewire ativo.
- Evita selecionar textarea oculto quando existem modais/componentes antigos no DOM.
- Le diretamente o runtime do Livewire antes dos fallbacks de HTML.
- Aguarda sincronizacao de nfs.description antes de vencimento/anexos.
- Confere a Observacao novamente apos upload dos PDFs.

## 0.8.9

- suporte ao novo fluxo `Enviar nota importada (NFS-E)`;
- procura a NFS-e atual em `Situação de Entrada = Não possui` antes de criar novo lançamento;
- valida número + empresa/filial + CNPJ fornecedor + valor + emissão;
- completa no registro importado apenas aprovador, observação, anexos e vencimento;
- mantém a busca da observação histórica exclusivamente em registros `Efetuada`;
- evita lançamento duplicado quando o Agilize já importou a NFS-e.
