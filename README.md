# Automação Agilize

## v0.9.11 — localizar pré-cadastro com número incorreto e publicar código no GitHub

A procura da nota atual ganhou um fallback seguro para o caso em que o Agilize pré-cadastra o número com um prefixo indevido. Exemplo tratado: **NFS-e 2721** aparecendo na lista como **2600000002721**. Quando a busca pelo número exato falha, a automação pesquisa o fornecedor em **Notas NFS-E** incluindo o mês atual e os 3 meses anteriores. A linha só é reutilizada quando número por sufixo, empresa, fornecedor, valor e emissão conferem.

O `FERRAMENTAS\07_PUBLICAR_VERSAO.bat` também foi reforçado. Agora ele funciona mesmo quando o projeto veio de ZIP sem `.git`, preserva o histórico de `origin/main`, cria o commit da versão e **exige que o push do código-fonte seja concluído antes de publicar a Release**. Assim o repositório não fica parado em uma versão antiga enquanto o instalador avança.

## v0.9.10 — pesquisa com estabilização do Livewire

Nesta versão, as pesquisas aguardam um pouco mais o Livewire e a grade terminarem de renderizar antes de ler os resultados. Isso evita avançar enquanto a pesquisa ainda não apareceu visualmente no navegador.

A busca de observação em **Notas NFS-E** agora cobre os **3 meses completos anteriores** ao mês da nota atual (mês anterior + 2 meses extras). Os campos de data também são conferidos após o Livewire atualizar a tela e reaplicados se o Agilize restaurar o período padrão.

## v0.9.8 — lotes mais rápidos e tratamento de registros já enviados

A v0.9.8 corrige os erros observados em lotes grandes depois que várias notas já estavam no Agilize. Registros em **Aguardando Aprovação** ou **Efetuada** são reconhecidos como já processados e a fila segue para o próximo item sem tentar reenviar anexos ou procurar observação novamente.

Principais ajustes:

- mantém o processamento **1 por vez** para estabilidade;
- verifica primeiro se a nota atual já está lançada;
- pula automaticamente registros em **Aguardando Aprovação / Efetuada**;
- reforça a abertura de **Editar / Ver nota** para botões que agora aparecem apenas como ícone;
- em registros existentes editáveis, a ausência do campo **Anexo** não derruba o lote quando o Agilize não oferece esse campo;
- para **Não possui**, o anexo continua obrigatório e a busca é repetida especificamente nesse status quando necessário;
- reduz reloads redundantes de `/nfs` e reaproveita referências históricas em cache;
- remove a aba **E-mail / Downloads** da interface;
- mantém **Ver detalhes / Copiar detalhes** para diagnóstico de lotes.

Detalhes: `DOCUMENTACAO/CORRECOES_V098.md`.

## v0.9.4 — editar registro existente antes de criar nova NFS-e

- Se o número da nota já existir no Agilize, o sistema abre **Editar / Ver nota** independentemente da Situação de Entrada.
- Uma nova NFS-e só é criada depois de buscas ampliadas não encontrarem nenhum registro com o mesmo número.
- Divergências secundárias de valor/data/status não autorizam duplicar uma nota existente.

## v0.9.3 — pareamento Auditor 2894 e pré-lançamentos do Agilize

- Corrige o pareamento da NFS-e `2894`: recibo/boleto + DANFSe oficial agora formam **1 lançamento com 2 PDFs**.
- Adiciona a filial `LCR COMERCIO DE MOVEIS LTDA (0029-40)` / `09.081.947/0029-40` (`company_id 42`).
- O parser passa a separar explicitamente CNPJ de **tomador/cliente** e **fornecedor**, inclusive quando uma filial nova ainda não está no mapa local.
- Em NFS-E, antes de criar um novo lançamento, o sistema procura a nota atual já pré-lançada em **Situação de Entrada = Não possui** e, se os dados conferirem, complementa esse registro.
- O ID de uma filial nova também pode ser resolvido diretamente pelo select de empresas exibido no Agilize.

## v0.9.2 — janela de 2 meses em Doc. - Contas a pagar

- Em `Doc. - Contas a pagar`, a pesquisa histórica continua sendo pelo **nome do fornecedor/beneficiário**.
- Antes de pesquisar o nome, a automação altera o período para **hoje - 2 meses até hoje**.
- Os filtros de data são preenchidos por último, depois de empresa e tipo de pesquisa, para evitar que o Livewire restaure a data do dia.
- O sistema aguarda o debounce dos campos e confere os valores que realmente ficaram na tela; se o Agilize restaurar as datas, elas são reaplicadas.
- Em `Notas NFS-E`, permanece a regra anterior de pesquisa no mês anterior.

## v0.9.1 — pesquisa histórica correta em Contas a pagar

- Em `Doc. - Contas a pagar`, a busca da observação anterior é feita pelo **nome do fornecedor/beneficiário**.
- Para a LOL, a chave de pesquisa é `LOL SERVIÇOS DE INTERNET LTDA`.
- O número da nota/fatura continua sendo usado para localizar o lançamento atual, mas não para buscar a observação histórica.
- Em `Notas NFS-E`, a busca histórica continua por CNPJ do fornecedor.


## v0.8.9 — destino correto para Doc. - Contas a pagar

- A seleção `Doc. - Contas a pagar` agora controla o **destino final** do lançamento, não apenas a pesquisa histórica.
- No modo **Automático**, Notas de Débito da LOL (`09.267.506/0001-36`) são direcionadas para `/documentos`.
- A observação/aprovador pode ser localizada em NFS-E como referência histórica sem fazer o lançamento atual mudar para NFS-E.
- Se o formulário de `/documentos` não puder ser reconhecido, a automação mantém a área correta aberta e interrompe o processo; não cria NFS-E por engano.

## v0.8.6 — histórico somente com Situação de Entrada Efetuada

- A busca da nota-base do mês anterior agora força **Situação de Entrada = Efetuada**.
- Registros **Não possui**, Aguardando Entrada e outras situações são descartados mesmo se o Livewire não mantiver o filtro.
- A empresa/filial também é validada antes de reaproveitar observação e aprovador.

## v0.8.5 — compatibilidade com o novo modal de notas do Agilize

- Pareia NFS-e 2657 com boleto Sicoob pelo **Nº do Documento 2657**.
- Corrige leitura do CNPJ do beneficiário usando validação real dos dígitos do CNPJ.
- Corrige o layout da Prefeitura de Linhares, em que a extração textual pode inverter Nº da Nota e RPS.
- Documentos com **"Este documento não tem valor fiscal"** são tratados apenas como referência: não criam lançamento e não são anexados ao Agilize.
- Mantém o demonstrativo associado internamente ao lançamento quando número, empresa, fornecedor e valor confirmam o vínculo.

## v0.8.3 — atualização simples por GitHub Release

O atualizador agora usa somente a **última GitHub Release**. `VERSAO.txt` e GitHub Actions não participam mais da decisão de atualização. Uma nova versão só aparece no aplicativo quando a Release já contém `AutomacaoAgilize-Setup.exe` e o arquivo `.sha256`.

Para publicar, use `FERRAMENTAS\07_PUBLICAR_VERSAO.bat <versão>`. O instalador é gerado localmente e enviado pronto para a Release pelo GitHub CLI.

## v0.8.2 — observação completa herdada do mês anterior

A observação da nota-base agora é reaproveitada integralmente. O sistema não recria mais apenas os blocos de pagamento e rateio: preserva textos operacionais, instruções e rateios e atualiza somente informações confiáveis encontradas nos PDFs atuais, como vencimento, meio de pagamento/banco, referência mensal e identificadores de cobrança quando esses campos já existirem na observação-base.

Exemplo FINNET: `Meio de Pagamento: Boleto Bancário Bradesco (Obter no DDA)` é preservado, enquanto a data de vencimento e a referência mensal são atualizadas com o documento atual.

## v0.8.1 — atualização automática de ponta a ponta

A publicação de uma nova versão agora gera automaticamente a GitHub Release e os arquivos `AutomacaoAgilize-Setup.exe` + `.sha256`. Enquanto o GitHub Actions estiver construindo o instalador, a aba **Atualizações** oferece **Aguardar instalador**; quando a Release termina, o sistema baixa, valida e instala sem exigir uma nova tentativa manual.

Para publicar uma versão nova use `FERRAMENTAS\07_PUBLICAR_VERSAO.bat <versão>`. Não é mais necessário criar a tag manualmente.

## v0.8.0 — motor de pareamento multi-fornecedor

Esta versão generaliza o vínculo entre nota e boleto. O agrupamento deixa de depender de um único número ou do nome do arquivo e passa a usar evidências documentais: Nº NFS-e, Nota Fiscal referenciada no boleto, Fatura, RPS, Nº do Documento, CNPJ do fornecedor, CNPJ da empresa e valor.

Foram validados cenários reais de Auditor, FINNET, LOL Serviços de Internet e SKYTEF, inclusive documentos sem par.

Aplicativo Windows para preparar lançamentos no Agilize a partir de PDFs, mantendo o envio final sob responsabilidade do usuário.

## v0.7.4 — pareamento FINNET por Nota Fiscal

A fila agora reconhece boletos FINNET que trazem explicitamente no rodapé os campos `NOTA FISCAL` e `FATURA`. O campo `NOTA FISCAL` tem prioridade para relacionar o boleto ao PDF fiscal, mesmo que o `Nosso Número` seja diferente.

Exemplos validados:

- boleto `02343301` + nota `0047736` => lançamento `47736`;
- boleto `02343401` + nota `0047737` => lançamento `47737`.

Também foi corrigida a leitura de `VALOR A PAGAR`, evitando capturar o primeiro item de serviço quando a cobrança possui vários itens.

## v0.7.3 — fila por referência + notas de débito + ambiente de teste

A aplicação agora trabalha com **1 ou mais PDFs**. Os arquivos podem ser arrastados juntos ou em várias etapas e a ordem não importa.

O sistema:

1. lê todos os PDFs;
2. identifica o Nº NFS-e quando disponível;
3. relaciona nota, recibo e boleto do mesmo número;
4. cria uma fila de lançamentos;
5. permite preparar um lançamento selecionado ou todos;
6. abre cada formulário no Agilize e o documento correspondente para conferência;
7. não espera o envio manual de uma nota para preparar a próxima.

Se existir apenas nota ou apenas boleto, o lançamento continua disponível e recebe aviso para conferência.

## Pesquisa de histórico

A tela possui as mesmas áreas usadas no Agilize:

- Notas NFS-E
- Doc. - Contas a pagar

A seleção define onde o sistema pesquisa o CNPJ primeiro. Se não encontrar, tenta automaticamente a outra área antes de desistir. NF-e/CT-e não participa da pesquisa histórica.

## Estado atual dos tipos

- **NFS-E:** leitura + pesquisa de histórico + preenchimento automático completo.
- **NF-e/CT-e:** não participa da pesquisa de histórico.
- **Doc. - Contas a pagar:** participa da pesquisa de histórico; adaptador de criação preparado para evolução.

Para mapear o preenchimento das duas últimas áreas é necessário capturar os formulários/HAR dessas telas, pois os seletores não estavam presentes no HAR original de NFS-E.

## Atualizacoes v0.7.1

O atualizador agora usa **GitHub Releases como fonte oficial**, seguindo o mesmo principio do projeto Monitor Carat + PDV. Falhas esperadas como repositorio ainda nao publicado, ausencia de Release, internet indisponivel ou limite temporario do GitHub nao sao mais exibidas como erro da aplicacao.

O botao **Atualizar agora** somente e habilitado quando a Release possuir `AutomacaoAgilize-Setup.exe` e `AutomacaoAgilize-Setup.exe.sha256`.


## Build

Use:

`FERRAMENTAS\05_GERAR_INSTALADOR.bat`

O instalador final é gerado em:

`installer\output\AutomacaoAgilize-Setup.exe`

## Notas de débito / Internet

A v0.7.3 reconhece notas de débito e boletos de internet mesmo quando não existe Nº NFS-e.
O relacionamento usa, nesta ordem, Nº NFS-e, Fatura e Nº do documento do boleto.
Boletos sem CNPJ do pagador podem ser associados pela identificação conhecida da empresa.

A pesquisa de histórico não usa mais **Notas NF-e/CT-e (DANFE)**. A busca fica restrita a:

1. Notas NFS-E
2. Doc. - Contas a pagar

A ordem entre essas duas áreas depende da opção escolhida e do tipo de documento reconhecido.

## Ambiente de teste

Para testar contra o Agilize de desenvolvimento sem alterar a configuração de produção, execute:

```bat
EXECUTAR_AMBIENTE_TESTE.bat
```

Esse BAT aponta o mesmo código para:

```text
https://dev-ml.startinghub.com.br
```

e guarda perfil, credenciais e logs de teste separadamente em:

```text
%LOCALAPPDATA%\AutomacaoAgilize-Teste
```

A execução normal continua usando `https://moveis-linhares.startinghub.com.br`.


## Atualizador v0.7.3

O verificador diferencia repositorio inexistente/privado de repositorio existente sem Release. Consulte `DOCUMENTACAO/CORRECOES_V073.md`.

### v0.8.7 - Observacao no Agilize atualizado
A leitura do historico agora usa o componente Livewire ativo e o preenchimento da Observacao e validado antes e depois do upload dos anexos. Veja `DOCUMENTACAO/CORRECOES_V087.md`.

### v0.8.9 - NFS-e já importada pelo Agilize

Quando a NFS-e atual já aparecer na lista com **Situação de Entrada = Não possui**, a Automação Agilize não abre um segundo lançamento. Ela confirma Número, Empresa/filial, CNPJ fornecedor, Valor e Emissão e completa o modal **Enviar nota importada (NFS-E)** com observação histórica atualizada, aprovador, anexos e vencimento. Se não houver registro importado correspondente, usa o fluxo normal de `Enviar Nota`.
