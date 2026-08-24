# Correções v0.8.4 - Starting Hub / Sicoob e demonstrativo informativo

## Caso analisado

Foram usados três documentos referentes à mesma cobrança:

- NFS-e fiscal nº **2657**, emitida pela STARTING HUB DE INOVACAO LTDA;
- boleto Sicoob cujo **N. documento = 2657**;
- demonstrativo da NFS-e nº **2657**, marcado explicitamente como **"Este documento não tem valor fiscal"**.

O comportamento correto é gerar **1 lançamento**, anexando somente a NFS-e fiscal e o boleto. O demonstrativo serve apenas como referência interna.

## Regras implementadas

### Pareamento NFS-e x boleto

Nova evidência forte:

```text
Número fiscal da nota == N. documento do boleto
2657                  == 2657
```

Esse vínculo recebe prioridade alta no motor de correlação.

### Layout da Prefeitura de Linhares

Nesse PDF, a extração textual pode inverter a posição visual do RPS e do número fiscal. O parser agora reconhece o layout e resolve corretamente:

```text
NFS-e: 2657
RPS:   2670
```

### CNPJ válido

Foi incluída validação dos dígitos verificadores do CNPJ. Isso impede que partes de linha digitável/código de barras sejam confundidas com CNPJ.

Exemplo rejeitado corretamente:

```text
15.600.000/1621-00
```

Fornecedor correto:

```text
46.882.111/0001-70
STARTING HUB DE INOVACAO LTDA
```

### Demonstrativo sem valor fiscal

Documentos contendo simultaneamente:

```text
DEMONSTRATIVO DA NOTA FISCAL
ESTE DOCUMENTO NÃO TEM VALOR FISCAL
```

são classificados como **somente referência**.

Eles:

- não criam um lançamento separado;
- não entram na lista de anexos do Agilize;
- não são abertos como documento principal de conferência;
- podem ser associados internamente ao lançamento correspondente para diagnóstico/conhecimento.

### Outros ajustes

- boleto Sicoob agora identifica corretamente `N. documento = 2657`, em vez de confundir CEP;
- `Nosso Número = 2709-0` passa a ser reconhecido;
- banco identificado como `Sicoob / 756`;
- vencimento identificado como `05/09/2026`;
- valor identificado como `R$ 1.621,00`;
- referência abreviada `Ref. Ago/2026` é normalizada para `Agosto/2026`;
- nome do pagador não pode substituir o nome do fornecedor quando as colunas do boleto forem extraídas fora de ordem.

## Resultado esperado com os três PDFs

```text
Lançamento 2657
├── NFS-e fiscal 2657              -> ANEXAR
├── boleto Sicoob / doc. 2657      -> ANEXAR
└── demonstrativo NFS-e 2657       -> REFERÊNCIA, NÃO ANEXAR
```

Dados principais:

```text
Número:          2657
Fornecedor:      STARTING HUB DE INOVACAO LTDA
CNPJ fornecedor: 46.882.111/0001-70
Empresa:         LCR COMERCIO DE MOVEIS LTDA (0001-49)
CNPJ empresa:    09.081.947/0001-49
Valor:           R$ 1.621,00
Emissão:         21/08/2026
Vencimento:      05/09/2026
Banco:           Sicoob
Nosso número:    2709-0
Referência:      Agosto/2026
```
