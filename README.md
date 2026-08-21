# Automação Agilize

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