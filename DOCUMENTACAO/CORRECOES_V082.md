# Automação Agilize v0.8.2 - Observação completa

## Regra nova

Ao localizar a nota-base do mês anterior, a aplicação lê a **observação inteira** e usa esse texto como modelo do lançamento atual.

A aplicação preserva:

- estrutura e quebras de linha;
- rateio;
- instruções internas;
- textos como `(Obter no DDA)`;
- observações livres não relacionadas a dados extraídos do PDF.

Só são atualizados campos que o PDF atual fornece com segurança e que já aparecem rotulados na observação-base:

- vencimento / data de vencimento;
- padrão `BOLETO dd/mm/aaaa`;
- meio de pagamento e banco;
- referência mensal (`Ref. Julho/2026`, por exemplo);
- número do documento;
- nosso número;
- valor do documento / valor a pagar;
- número da nota/NFS-e quando houver rótulo explícito.

## Exemplo FINNET

Observação-base:

```text
- DADOS PARA PAGAMENTO:
Ref. Junho/2026
Data de Vencimento: 28/07/2026
Meio de Pagamento: Boleto Bancário Bradesco (Obter no DDA)

- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):
LOJA
```

Com um PDF atual contendo `Ref. Julho/2026` e vencimento `28/08/2026`, o resultado é:

```text
- DADOS PARA PAGAMENTO:
Ref. Julho/2026
Data de Vencimento: 28/08/2026
Meio de Pagamento: Boleto Bancário Bradesco (Obter no DDA)

- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):
LOJA
```

O rateio e a instrução `(Obter no DDA)` não são recriados nem removidos.

## Segurança da substituição

A aplicação não substitui datas indiscriminadamente. Uma data em texto livre ou dentro do rateio permanece intacta. A alteração de data é limitada a linhas identificadas como vencimento ou pagamento.
