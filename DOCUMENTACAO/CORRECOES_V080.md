# Correções v0.8.0 — Pareamento multi-fornecedor

## Objetivo

Evitar que nota e boleto do mesmo lançamento sejam separados e, ao mesmo tempo, impedir que PDFs de fornecedores diferentes sejam unidos apenas porque possuem a mesma filial, nome parecido ou nome de arquivo semelhante.

## Ordem de evidências

1. Boleto com `NOTA FISCAL` explícita -> Nº fiscal da nota.
2. Mesmo Nº NFS-e entre nota e recibo/boleto.
3. RPS da nota -> Nº do Documento do boleto sem parcela (`991483` x `991483-01`).
4. Fatura da Nota de Débito -> Nº do Documento do boleto (`208938` x `208938`).
5. DPS -> Nº do Documento, quando aplicável.
6. Fallback somente quando fornecedor + empresa + valor coincidem e há um único candidato.

## Travas contra falso pareamento

O vínculo é recusado quando ambos os PDFs possuem informação e há divergência em:

- CNPJ do fornecedor;
- CNPJ da empresa/tomador;
- valor do documento.

O nome do arquivo nunca é usado como prova de vínculo.

## Casos validados

- Auditor: DANFSe + recibo/boleto pelo Nº NFS-e.
- FINNET: boleto contendo `NOTA FISCAL` + NFS-e correspondente.
- LOL Serviços de Internet: Nota de Débito por `Fatura` + boleto por `Nº do Documento`.
- SKYTEF: NFS-e com `RPS` + boleto cujo documento possui o RPS com sufixo de parcela.
- Nota ou boleto sem par permanece como lançamento independente.
