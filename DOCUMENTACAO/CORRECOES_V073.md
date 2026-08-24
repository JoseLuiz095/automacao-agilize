# Correcoes v0.7.3 - Atualizador GitHub

## Problema corrigido

O endpoint `releases/latest` do GitHub pode responder HTTP 404 em duas situacoes diferentes:

1. o repositorio nao esta acessivel ao cliente;
2. o repositorio existe, mas ainda nao possui uma Release publicada.

A versao anterior tratava ambos os cenarios como se o repositorio nao existisse. Alem disso, o fallback tentava ler `VERSAO.txt` apenas em `main` e `master`, usando `raw.githubusercontent.com`, o que podia gerar outro 404 mesmo em um repositorio existente.

## Fluxo v0.7.3

1. Consulta a ultima Release.
2. Se a Release existe, ela continua sendo o canal autoritativo para instalar atualizacoes.
3. Se `/releases/latest` responde 404, consulta os metadados do repositorio separadamente.
4. Se o repositorio existe, descobre a branch padrao real.
5. Le `VERSAO.txt` pela GitHub Contents API usando essa branch.
6. Se o repositorio existe mas ainda nao possui Release, mostra estado `Repositorio conectado`, e nao `Repositorio nao encontrado`.
7. Se o repositorio for privado, aceita autenticacao opcional por `AUTOMACAO_AGILIZE_GITHUB_TOKEN` ou `GITHUB_TOKEN`.
8. Como contingencia de desenvolvimento, tenta `git clone --depth 1`; isso funciona quando o Windows ja esta autenticado no Git Credential Manager.

## Repositorio privado

Um executavel distribuido para usuarios finais nao deve conter um Personal Access Token embutido. Portanto, para atualizacao automatica sem credenciais por maquina, o repositorio/canal que publica `AutomacaoAgilize-Setup.exe` e o `.sha256` precisa ser acessivel publicamente.

Se o codigo-fonte precisar permanecer privado, a recomendacao e usar um repositorio publico separado somente para Releases.

## Assets esperados em cada Release

- `AutomacaoAgilize-Setup.exe`
- `AutomacaoAgilize-Setup.exe.sha256`

Sem os dois arquivos a versao pode ser detectada, mas o botao `Atualizar agora` permanece desabilitado por seguranca.
