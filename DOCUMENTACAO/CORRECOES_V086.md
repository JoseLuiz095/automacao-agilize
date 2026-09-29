# Correções v0.8.6

## Histórico da observação: usar somente notas Efetuadas

Após a atualização do Agilize, a pesquisa por CNPJ passou a devolver registros de várias situações. A automação podia selecionar o registro mais recente com **Situação de Entrada = Não possui**, abrir o modal e não obter a observação esperada.

A v0.8.6 passa a:

1. selecionar explicitamente **Situação de Entrada = Efetuada** no filtro `#status` da tela de NFS-e;
2. continuar validando cada linha retornada e rejeitar qualquer linha cuja situação não seja **Efetuada**, mesmo se o filtro visual falhar ou o Livewire sofrer novo rerender;
3. validar também a empresa/filial da linha, evitando reaproveitar observação de outra filial que use o mesmo CNPJ de fornecedor;
4. registrar no log quando uma linha é descartada por situação ou empresa.

No Agilize atual, o filtro possui `filter.status`, com `-1 = Não possui` e `99 = Efetuada`.

## Fluxo esperado

```
Empresa atual + CNPJ fornecedor + mês anterior
        ↓
Situação de Entrada = Efetuada
        ↓
mesma empresa/filial
        ↓
registro mais recente válido
        ↓
Editar / Ver nota
        ↓
ler observação completa + aprovador
```
