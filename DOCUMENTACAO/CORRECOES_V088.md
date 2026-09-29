# Correções v0.8.8 - NFS-e importada / situação "Não possui"

O Agilize passou a importar algumas NFS-e antes do lançamento manual. Nesses casos a lista já contém a nota com **Situação de Entrada = Não possui** e, ao abrir o registro, aparece o modal **Enviar nota importada (NFS-E)** com Número, Valor, Emissão, Empresa, CNPJ e Nome do fornecedor já preenchidos.

## Nova regra

A automação continua buscando a **observação e o aprovador no histórico Efetuado do mês anterior**. Depois disso, antes de clicar em `Enviar Nota`, ela procura a própria nota atual na lista com status `Não possui`.

A linha só é aceita quando coincidem:

- Número da nota (zeros à esquerda são ignorados);
- empresa/filial;
- CNPJ do fornecedor;
- valor, quando disponível;
- data de emissão, quando disponível;
- situação `Não possui`.

Se a linha correta existir, o sistema abre o registro importado e preenche somente os campos ainda pendentes:

- Usuário para aprovação;
- Observação;
- Anexo(s);
- Data de vencimento.

Os dados fiscais já importados não são reescritos. O envio final continua manual.

Se nenhuma linha importada correspondente for encontrada, o fluxo antigo permanece: abrir `Enviar Nota` e criar o formulário normalmente.

## Proteção contra duplicidade

Um registro com o mesmo número, mas empresa, fornecedor, valor ou emissão divergentes, é rejeitado. Isso evita completar a nota errada apenas porque o número coincide.
