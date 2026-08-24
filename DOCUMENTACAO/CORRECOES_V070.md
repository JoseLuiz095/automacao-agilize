# Correções e evolução v0.7.0

## Fila em massa

- a tela aceita 1 ou mais PDFs (limite operacional de 100 por fila);
- os documentos são agrupados automaticamente pelo Nº NFS-e;
- a ordem dos PDFs não importa;
- nota + boleto da mesma NFS-e formam um único lançamento;
- se só existir nota ou só boleto, o lançamento continua existindo com aviso;
- cada grupo anexa todos os PDFs relacionados.

## Lançamentos independentes

A automação do navegador agora trabalha em uma fila própria. Depois de preparar um formulário, o aplicativo não espera o envio manual para preparar o próximo. Cada lançamento recebe o status:

- Pronto;
- Na fila;
- Preparando;
- Aberto para conferência;
- Erro / Revisar dados.

Isso elimina o bloqueio em que era necessário enviar ou fechar o navegador antes de iniciar outro lançamento.

## Pesquisa de histórico em múltiplas áreas

A interface replica as três áreas do Agilize usadas no processo:

- Notas NF-e/CT-e (DANFE);
- Notas NFS-E;
- Doc. - Contas a pagar.

O usuário pode indicar onde pesquisar primeiro. Se não houver registro para o CNPJ/empresa no mês anterior, a automação continua nas demais áreas.

A busca tenta recuperar RATEIO e aprovador quando a tela encontrada disponibiliza esses campos.

## Estrutura para outros tipos de envio

A v0.7.0 separa:

- agrupamento de documentos (`batch.py`);
- catálogo de módulos do Agilize (`tipos_agilize.py`);
- sessão/fila do navegador (`agilize_batch.py`);
- automação específica do formulário NFS-E (`agilize.py`).

O preenchimento automático integral continua mapeado para NFS-E. As rotas de NF-e/CT-e e Contas a pagar já participam da pesquisa de histórico. Para automatizar também os formulários de criação dessas duas áreas com a mesma confiabilidade, é necessário mapear o HTML/HAR das telas de criação correspondentes.
