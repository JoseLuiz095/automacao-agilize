# Correcoes v0.7.3 - Internet, pesquisa e ambiente de teste

- Corrigido reconhecimento de NOTA DE DEBITO e boletos de internet.
- Pareamento por Fatura / Numero do documento, alem do Nº NFS-e.
- Corrigido falso positivo de CTE causado pela substring em palavras comuns.
- Pesquisa de historico limitada a Notas NFS-E e Doc. - Contas a pagar.
- NF-e/CT-e (DANFE) nao participa mais da pesquisa de CNPJ/rateio.
- Corrigido vencimento em boletos Banco do Brasil: usa a data de vencimento, nao a data do documento.
- Adicionado reconhecimento do pagador em boletos sem CNPJ do tomador.
- Adicionado FERRAMENTAS/10_EXECUTAR_AMBIENTE_TESTE.bat apontando para https://dev-ml.startinghub.com.br.
- Ambiente de teste usa dados separados em %%LOCALAPPDATA%%\AutomacaoAgilize-Teste.
