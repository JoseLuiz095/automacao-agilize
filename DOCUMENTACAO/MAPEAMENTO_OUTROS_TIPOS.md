# Mapeamento de outros tipos de lançamento

A v0.7.0 já conhece as três rotas do menu do Agilize:

| Tipo | Rota | Pesquisa de histórico | Criação automática |
| --- | --- | --- | --- |
| Notas NF-e/CT-e (DANFE) | `/notas` | Sim, fallback genérico | A mapear |
| Notas NFS-E | `/nfs` | Sim | Sim |
| Doc. - Contas a pagar | `/documentos` | Sim, fallback genérico | A mapear |

O HAR original usado no desenvolvimento contém o formulário completo de `/nfs`, mas não contém os formulários de criação de `/notas` e `/documentos`.

Para habilitar preenchimento completo nessas duas áreas, capture um HAR de cada fluxo:

1. abrir a área;
2. clicar no botão de novo envio;
3. preencher um exemplo sem confirmar o envio;
4. salvar o HAR.

Depois disso devem ser criados adaptadores específicos, mantendo a fila, agrupamento e busca histórica já existentes.
