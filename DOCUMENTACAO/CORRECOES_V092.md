# Correções v0.9.2 — período histórico em Doc. - Contas a pagar

## Problema

A tela `Doc. - Contas a pagar` abre com o filtro de data iniciado no dia atual. Mesmo pesquisando corretamente pelo nome do fornecedor, como `LOL SERVIÇOS DE INTERNET LTDA`, os lançamentos anteriores ficavam fora do período e a grade retornava vazia.

## Regra nova

Para `Doc. - Contas a pagar`:

1. resolve o destino do lançamento;
2. seleciona empresa e pesquisa por nome do fornecedor;
3. ajusta a data inicial para **dois meses de calendário antes de hoje**;
4. ajusta a data final para **hoje**;
5. aguarda o debounce/Livewire;
6. confere os valores efetivamente exibidos nos campos;
7. somente então pesquisa o fornecedor.

Exemplo em 04/09/2026:

- início: `04/07/2026` (`2026-07-04` no campo HTML);
- fim: `04/09/2026` (`2026-09-04`).

A pesquisa continua pelo **nome do fornecedor**, não pelo CNPJ nem pela fatura.

Para `Notas NFS-E`, o intervalo continua restrito ao mês anterior.

## Log esperado

```text
Pesquisando fornecedor por NOME em Doc. - Contas a pagar...
Doc. - Contas a pagar: valor de busca historica = 'LOL SERVICOS DE INTERNET LTDA' (nome do fornecedor).
Doc. - Contas a pagar: datas confirmadas na tela = 2026-07-04 ate 2026-09-04.
Doc. - Contas a pagar: periodo de pesquisa ajustado para 2026-07-04 ate 2026-09-04 (ultimos 2 meses).
Doc. - Contas a pagar: campo Buscar confirmado com o nome 'LOL SERVICOS DE INTERNET LTDA'.
```
