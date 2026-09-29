# Correções v0.9.6 — processamento sequencial da fila

## Motivo

A estratégia da v0.9.5 permitia vários formulários simultâneos. Embora limitasse a quantidade de abas, a experiência ficou confusa e ainda mantinha consumo elevado de recursos.

## Nova regra

- A fila pode receber dezenas de lançamentos normalmente.
- O navegador prepara **somente 1 lançamento por vez**.
- Enquanto o formulário atual estiver aberto, os demais permanecem na fila.
- Ao enviar, cancelar ou fechar o formulário atual, a automação fecha as abas auxiliares daquele lançamento e libera o próximo automaticamente.
- O envio final continua manual.

## Interface

O botão passou a indicar `PREPARAR TODOS (1 POR VEZ)` e, quando houver mais de um lançamento, é exibido um aviso antes de iniciar a fila.

## Estabilidade

Com apenas um lançamento ativo, o navegador mantém no máximo o formulário atual e sua aba de conferência, reduzindo significativamente o risco de `ERR_INSUFFICIENT_RESOURCES`.
