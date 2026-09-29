# Correções v0.9.1

## 1. Pesquisa histórica em Doc. - Contas a pagar

- O destino é resolvido **antes** da pesquisa histórica.
- Nota de débito / fornecedor LOL (`09.267.506/0001-36`) no modo Automático é resolvida como `Doc. - Contas a pagar` antes de qualquer pesquisa.
- Quando o destino é `Doc. - Contas a pagar`, a pesquisa histórica usa somente o **nome do fornecedor/beneficiário** (`provider_name` / `beneficiario_nome`).
- Para essa área, não há fallback automático para NFS-E; portanto a busca não troca o nome por CNPJ.
- O sistema confirma no log o valor efetivamente presente em `#searchInput`.

Exemplo esperado:

```text
Destino resolvido antes da pesquisa historica: Doc. - Contas a pagar.
Pesquisando fornecedor por NOME em Doc. - Contas a pagar...
Doc. - Contas a pagar: valor de busca historica = 'LOL SERVICOS DE INTERNET LTDA' (nome do fornecedor).
Doc. - Contas a pagar: campo Buscar confirmado com o nome 'LOL SERVICOS DE INTERNET LTDA'.
```

## 2. Erro Playwright TargetClosed

Foi tratado o erro:

```text
Target page, context or browser has been closed
```

A fila agora:

1. identifica que o contexto do navegador morreu;
2. fecha resíduos do Playwright;
3. recria o perfil/contexto persistente;
4. repete o mesmo lançamento uma vez;
5. se ainda falhar, marca somente aquele grupo como erro e cria uma sessão nova para o próximo.

Isso evita o efeito em cascata em que todos os lançamentos seguintes falhavam porque a fila continuava reutilizando um contexto já fechado.
