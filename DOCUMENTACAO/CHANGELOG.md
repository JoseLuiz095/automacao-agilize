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
