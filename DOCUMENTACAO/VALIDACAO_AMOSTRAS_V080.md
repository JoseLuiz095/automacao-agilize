# Validação das amostras reais — v0.8.0

A v0.8.0 foi validada contra os PDFs reais fornecidos durante a homologação.

## Regras confirmadas

- Auditor: DANFSe e recibo/boleto relacionados pelo mesmo número da NFS-e.
- FINNET: boleto que informa `NOTA FISCAL` relacionado diretamente ao número fiscal.
- LOL Serviços de Internet: Nota de Débito (`Fatura`) relacionada ao `Nº do Documento` do boleto.
- SKYTEF: NFS-e relacionada ao boleto pelo RPS. Exemplo: NFS-e 991482 possui RPS 991483 e o boleto possui documento 991483-01.
- Documento sem par permanece independente.
- Nome de arquivo não é usado como vínculo.
- Divergência de CNPJ do fornecedor, CNPJ da empresa ou valor impede pareamento automático.

## Resultado do lote mais recente

20 PDFs foram classificados em 14 lançamentos:

- 2605: 2 PDFs
- 2607: 2 PDFs
- 2609: 1 PDF
- 2431: 2 PDFs
- 2446: 1 PDF
- 2055: 1 PDF
- 2056: 2 PDFs
- 2057: 1 PDF
- 2054: 1 PDF
- 208929: 1 PDF
- 208938: 2 PDFs
- 991480: 1 PDF
- 991481: 1 PDF
- 991482: 2 PDFs

## Teste ampliado

Incluindo também os quatro PDFs FINNET da homologação anterior, 24 PDFs foram classificados em 16 lançamentos, sem mistura entre fornecedores.

## Caso negativo importante

Os arquivos de Jaguaré demonstram por que o nome do arquivo/filial não pode ser usado como chave:

- boleto LOL: fornecedor 09.267.506/0001-36, valor R$ 200,00;
- nota SKYTEF: fornecedor 04.988.631/0001-11, valor R$ 244,94.

Mesmo sendo da mesma filial Jaguaré, os documentos devem permanecer em lançamentos diferentes.
