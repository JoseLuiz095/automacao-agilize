# Correcoes v0.9.0 - Pesquisa historica em Doc. - Contas a pagar

## Problema
Para lancamentos de `Doc. - Contas a pagar`, a pesquisa da referencia historica estava usando uma chave inadequada para o fluxo operacional. Em documentos LOL, por exemplo, a pesquisa deve partir do fornecedor `LOL SERVICOS DE INTERNET LTDA`, e nao do numero da nota/fatura.

## Regra nova
- `Notas NFS-E`: pesquisa historica continua por CNPJ/documento do fornecedor.
- `Doc. - Contas a pagar`: pesquisa historica passa a usar o **nome do fornecedor/beneficiario**.
- Exemplo LOL: `LOL SERVICOS DE INTERNET LTDA`.
- Numero da nota/fatura continua sendo usado para identificar/complementar o lancamento atual, mas nao como chave principal para buscar a observacao anterior.
- A area em que a observacao for encontrada nao altera o destino atual do lancamento.

## Validacoes
Depois da pesquisa por nome, a automacao ainda usa os dados disponiveis da linha (fornecedor/CNPJ, empresa, periodo) como confirmacao antes de abrir o historico.
