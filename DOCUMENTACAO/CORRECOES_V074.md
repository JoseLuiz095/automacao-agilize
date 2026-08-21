# Correções v0.7.4 - Pareamento FINNET

## Problema

Quatro PDFs FINNET eram transformados em quatro lançamentos porque o boleto era identificado pelo `Nosso Número` (`02343301` / `02343401`) enquanto a nota era identificada pelo número fiscal (`47736` / `47737`).

## Regra nova

Para boletos/recibos que tragam explicitamente `NOTA FISCAL`, essa referência passa a ter prioridade sobre `FATURA`, `Nosso Número` e número genérico do documento.

### Par 1

- Nota fiscal: `0047736` => `47736`
- Boleto: `NOTA FISCAL 47736`
- Fatura: `23433`
- Nosso Número: `02343301`
- Valor: `751,40`
- Vencimento: `28/08/2026`

Resultado: **1 lançamento 47736 com 2 PDFs**.

### Par 2

- Nota fiscal: `0047737` => `47737`
- Boleto: `NOTA FISCAL 47737`
- Fatura: `23434`
- Nosso Número: `02343401`
- Valor: `3.001,78`
- Vencimento: `28/08/2026`

Resultado: **1 lançamento 47737 com 2 PDFs**.

## Validação secundária

Além do número da nota, os pares coincidem em fornecedor, tomador, vencimento e valor. Esses campos permanecem úteis para consistência, mas o vínculo explícito `NOTA FISCAL` do boleto é a chave mais forte.
