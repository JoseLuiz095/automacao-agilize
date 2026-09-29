# Correções v0.9.3 — pareamento Auditor 2894 + pré-lançamento "Não possui"

## 1. Por que a NFS-e 2894 virou dois lançamentos

O recibo/boleto da Auditor traz no mesmo PDF o CNPJ do cliente `09.081.947/0029-40` e o CNPJ do fornecedor `32.401.507/0001-43`.

A filial `09.081.947/0029-40` ainda não existia no mapa local de empresas. Por isso o parser não a reconhecia como tomador e podia interpretar o CNPJ do cliente como se fosse o fornecedor do recibo. O DANFSe oficial identificava corretamente o fornecedor `32.401.507/0001-43`; o motor então aplicava o veto de CNPJs divergentes e separava os PDFs.

A v0.9.3:

- adiciona a filial LCR `(0029-40)` com `company_id = 42`;
- reconhece explicitamente blocos `TOMADOR / ADQUIRENTE` e `CLIENTE` mesmo quando uma filial ainda não estiver no mapa;
- mantém CNPJ do tomador e CNPJ do fornecedor separados antes do pareamento;
- permite resolver um `company_id` novo diretamente pelas opções exibidas pelo Agilize.

Resultado esperado para os dois PDFs de setembro:

- Nº NFS-e: `2894`;
- empresa: `LCR COMERCIO DE MOVEIS LTDA (0029-40)`;
- CNPJ empresa: `09.081.947/0029-40`;
- fornecedor: `AS AUDITORIA SISTEMAS E REPRESENTAÇÕES LTDA EPP`;
- CNPJ fornecedor: `32.401.507/0001-43`;
- valor: `1.617,34`;
- vencimento: `30/09/2026`;
- arquivos: **2 PDFs em 1 lançamento**.

## 2. Pré-lançamentos do Agilize passaram a ser prioridade

Para NFS-e, antes de abrir o formulário genérico `Enviar Nota`, a automação procura a nota atual na lista com:

- número da nota atual;
- empresa/filial atual;
- fornecedor atual;
- período da emissão atual;
- `Situação de Entrada = Não possui`.

Se número, empresa, fornecedor, valor e emissão conferirem, o registro existente é aberto e apenas os campos complementares são alimentados:

- usuário para aprovação;
- observação herdada/atualizada;
- anexo(s);
- data de vencimento.

O fluxo de criação de uma nova NFS-e só é usado quando nenhum pré-lançamento compatível for encontrado.

## 3. Filiais novas

Se o PDF contiver um CNPJ de tomador que ainda não esteja no mapa local, o parser preserva o CNPJ/nome. Ao abrir o Agilize, a automação tenta encontrar a empresa correspondente nas opções do próprio select e memoriza o ID para o restante daquele processamento.
