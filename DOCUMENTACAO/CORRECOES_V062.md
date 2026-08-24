# Correções v0.6.2

## Documento único

O lançamento aceita **1 ou 2 PDFs**.

Com 1 PDF:

- o botão `PROCESSAR E ABRIR NO AGILIZE` fica habilitado;
- um aviso amarelo permanece visível na tela;
- ao clicar em processar, o usuário recebe uma confirmação antes de continuar;
- o mesmo PDF é usado como fonte de leitura, anexo e documento de conferência;
- se faltar algum dado obrigatório, o processamento informa exatamente o campo ausente.

Com 2 PDFs, o aviso desaparece e o comportamento continua normal.

## Atualizações

A atualização foi aproximada do comportamento do projeto Monitor Carat + PDV usado como referência.

O sistema agora:

1. verifica automaticamente alguns segundos após abrir;
2. consulta a última GitHub Release;
3. consulta também `VERSAO.txt` em `main`/`master` como fallback de detecção;
4. mostra um banner na tela principal quando existe versão mais nova;
5. destaca a aba **Atualizações** com a versão encontrada;
6. se houver `AutomacaoAgilize-Setup.exe`, oferece **Atualizar agora**;
7. se o código estiver mais novo mas o instalador ainda não existir, informa claramente que a Release ainda está sendo aguardada;
8. registra detalhes em `%LOCALAPPDATA%\AutomacaoAgilize\logs\update.log`.

A instalação automática continua dependendo de uma Release acessível contendo:

- `AutomacaoAgilize-Setup.exe`;
- preferencialmente `AutomacaoAgilize-Setup.exe.sha256`.

Se o repositório for privado, a aplicação não possui token embutido e o GitHub precisa ser acessível pelo método escolhido antes que a atualização automática funcione.
