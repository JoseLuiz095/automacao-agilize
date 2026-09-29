# Correções v0.9.4 — nunca duplicar uma NFS-e já existente

## Regra principal

Antes de abrir `Enviar Nota`, a automação pesquisa o **Número da nota** em **todos os status**.

Se existir qualquer registro com o mesmo número, ele é aberto em `Editar/Ver nota` e complementado. A situação de entrada (`Não possui`, `Efetuada`, `Aguardando...`) não bloqueia mais a reutilização do registro atual.

Uma nova NFS-e só pode ser criada quando nenhuma linha com o mesmo número for encontrada após três tentativas:

1. empresa correta + mês da emissão + todos os status;
2. mesma empresa + período ampliado;
3. período ampliado + todas as empresas.

## Quando existem vários registros com o mesmo número

O número continua sendo obrigatório e exato. Para escolher o melhor candidato, o sistema pontua:

- empresa/filial;
- CNPJ do fornecedor;
- valor;
- data de emissão;
- `Não possui` recebe pequena preferência apenas em caso de empate.

Divergências nesses dados **não autorizam criar uma duplicidade**. Elas são registradas no log e usadas somente para escolher o melhor registro.

## Segurança

Se o número já existe, mas o botão `Editar/Ver nota` não puder ser aberto após uma mudança do Agilize, o processo é interrompido. O sistema não cria outro lançamento como fallback.
