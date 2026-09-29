# Correções v0.9.10

## Espera adicional nas pesquisas do Agilize

A automação estava lendo a grade logo após o debounce/retorno do Livewire. Em algumas máquinas o navegador ainda não havia terminado de renderizar visualmente a nova pesquisa, o que podia fazer a rotina analisar linhas antigas ou uma grade ainda vazia.

Foi criado um tempo de estabilização específico para pesquisas/listagens:

- pesquisa histórica de NFS-e;
- pesquisa histórica em Doc. - Contas a pagar;
- procura do lançamento atual pelo número;
- segunda tentativa com Situação = Não possui;
- procura do documento atual em Contas a pagar.

A espera agora combina:

1. tempo mínimo um pouco maior para o debounce do Livewire;
2. `networkidle` quando disponível;
3. duas leituras consecutivas estáveis da tabela;
4. pequeno tempo final para renderização visual.

O atraso extra é aplicado apenas às pesquisas. O preenchimento dos campos do formulário continua usando a espera curta anterior para não tornar todo o processo lento.

## Janela de histórico

Permanece a regra da v0.9.9 para NFS-e: três meses completos anteriores ao mês da nota atual.
