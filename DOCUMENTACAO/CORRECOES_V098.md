# Correcoes v0.9.8

## Analise do lote informado

O log mostrou dois padroes principais de falha:

1. Registros em **Aguardando Aprovacao** eram tratados como se ainda precisassem ser preparados. Nessa situacao o Agilize pode ocultar a acao Editar e o campo Anexo. Agora esses registros sao reconhecidos como ja enviados, nao geram erro e a fila segue automaticamente.
2. Registros **Nao possui** ainda precisam ser complementados. A localizacao da acao foi ampliada para botoes/links por icone e para fallback de teclado na coluna de acoes. Quando necessario, a pesquisa e repetida especificamente com Situacao = Nao possui.

## Velocidade

- O sistema consulta a nota atual antes de procurar a observacao historica. Se ela ja estiver Aguardando Aprovacao/Efetuada, pula toda a pesquisa historica.
- Removido um reload redundante de /nfs por lancamento.
- Quando a pagina ja esta na area correta, ela e reutilizada em vez de navegar novamente.
- Referencias historicas iguais sao mantidas em cache por fornecedor + empresa + mes anterior.
- Tempos minimos de espera da pesquisa foram reduzidos mantendo margem para o debounce do Livewire.

## Anexos em registros existentes

Para registros editaveis que nao sejam `Nao possui`, a ausencia do campo Anexo deixa de abortar o grupo. O sistema registra a indisponibilidade e preserva o registro existente. Para `Nao possui`, o Anexo continua obrigatorio.

## E-mail / Downloads

A aba foi removida da interface. O foco volta a ser exclusivamente a fila de lancamentos, configuracoes e atualizacoes.
