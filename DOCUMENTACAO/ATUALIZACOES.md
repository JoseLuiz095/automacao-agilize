# Atualizações - fluxo v0.8.1

A fonte instalável continua sendo a GitHub Release. A diferença é que a Release agora é criada automaticamente pelo GitHub Actions quando `VERSAO.txt` muda em `main`.

Estados principais:

- **Sistema atualizado**: Release instalada é a mais recente.
- **Atualizar agora**: Setup.exe + SHA-256 já estão publicados.
- **Aguardar instalador**: `VERSAO.txt` é mais novo, mas o Actions ainda está montando a Release. O aplicativo pode acompanhar a publicação por até 10 minutos e prosseguir automaticamente.

Fluxo de publicação:

```text
07_PUBLICAR_VERSAO.bat
        -> push main / VERSAO.txt
        -> GitHub Actions
        -> PyInstaller
        -> Inno Setup
        -> Release vX.Y.Z
        -> Setup.exe + SHA-256
        -> Atualização disponível no aplicativo
```

---

# Atualizacoes

A Automacao Agilize usa **GitHub Releases** como canal oficial de atualizacao.

Repositorio configurado:

`JoseLuiz095/automacao-agilize`

## Release valida

Uma versao somente e considerada instalavel quando a Release mais recente possui:

- `AutomacaoAgilize-Setup.exe`
- `AutomacaoAgilize-Setup.exe.sha256`

O SHA-256 e validado antes de executar o instalador.

## Ordem de verificacao

1. consulta `releases/latest`;
2. se a Release nao estiver disponivel, consulta `VERSAO.txt` apenas como diagnostico/contingencia;
3. se o repositorio estiver indisponivel, o sistema mostra um estado neutro e continua funcionando normalmente.

O `VERSAO.txt` nunca substitui a necessidade de uma Release completa para instalar uma atualizacao.

## Interface

O banner da tela principal so aparece quando existe uma atualizacao realmente instalavel. Uma versao em preparacao, falta de internet, limite do GitHub ou repositorio ainda nao publicado ficam somente na aba Atualizacoes, sem parecer falha da aplicacao.

## Diagnostico

Execute:

`FERRAMENTAS\08_TESTAR_ATUALIZACAO.bat`

Log tecnico:

`%LOCALAPPDATA%\AutomacaoAgilize\logs\update.log`
