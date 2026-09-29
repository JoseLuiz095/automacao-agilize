# Correções v0.9.9

## Janela histórica de NFS-E

A pesquisa de observação em **Notas NFS-E** deixou de consultar somente o mês imediatamente anterior. Agora são consultados os **3 meses completos anteriores ao mês da nota atual**.

Exemplo para uma NFS-e emitida em 20/09/2026:

- início: 01/06/2026
- fim: 31/08/2026

Isso permite encontrar referências como as FINNET 47552/47553 de 20/07/2026 ao preparar as notas 47905/47906 de 20/09/2026.

## Confirmação do filtro de data

Depois de selecionar empresa, status e tipo de busca, a automação preenche as datas e lê novamente os dois campos visíveis. Se o Livewire restaurar as datas padrão, o intervalo é reaplicado antes de pesquisar o CNPJ do fornecedor.

## Cache

A chave de cache da referência histórica passou a usar a mesma janela efetivamente consultada, evitando reutilizar uma referência de um período incompatível.
