# Correções v0.9.11

## 1. NFS-e importada com número pré-cadastrado incorretamente

Cenário observado:

- número fiscal correto no PDF: `2721`;
- número existente no Agilize: `2600000002721`;
- fornecedor: `STARTING HUB DE INOVACAO LTDA`;
- situação do registro: `Não possui`.

A busca anti-duplicidade antiga procurava primeiro o número exato. Como `2721` e `2600000002721` são diferentes, o pré-cadastro podia não ser reconhecido. A pesquisa histórica por fornecedor também usa uma janela voltada às notas anteriores e, por definição, não inclui o mês atual. Isso é correto para copiar observação, mas não serve como contingência para localizar a própria nota atual.

### Regra nova

Quando o número exato não é encontrado, a automação executa uma contingência específica da nota atual:

1. permanece em **Notas NFS-E**;
2. usa **Todos os status**;
3. aplica a empresa/filial da nota;
4. pesquisa primeiro pelo CNPJ do fornecedor e depois pelo nome, quando disponível;
5. usa o período do **mês atual + 3 meses anteriores**;
6. aceita número com prefixo somente quando o número cadastrado termina no número fiscal esperado;
7. exige também empresa, fornecedor, valor e emissão iguais.

A equivalência por sufixo não é usada isoladamente. Também é exigido um prefixo adicional de pelo menos 4 dígitos para evitar confundir números comuns como `12721` e `2721`.

## 2. Publicação do código-fonte no GitHub

O repositório remoto ainda estava em `v0.8.4`, enquanto o projeto local já estava em `v0.9.10`. O publicador antigo só fazia `git push` quando a pasta já possuía um repositório Git compatível. Projetos extraídos de ZIP podiam gerar Release sem atualizar o código-fonte.

A v0.9.11 altera `FERRAMENTAS/07_PUBLICAR_VERSAO.bat` para:

- localizar/instalar Git e GitHub CLI;
- autenticar o GitHub CLI;
- inicializar `.git` quando necessário;
- configurar `origin` para `JoseLuiz095/automacao-agilize`;
- fazer `fetch origin main`;
- usar `origin/main` como pai do novo commit mantendo os arquivos atuais do projeto;
- criar uma branch local de backup quando já existir HEAD;
- criar o commit `Versao vX.Y.Z`;
- executar `git push origin main`;
- **bloquear a Release se o push falhar**.

Com isso, o mesmo BAT passa a atualizar código-fonte e Release em sequência, inclusive quando o desenvolvimento foi recebido em ZIP.
