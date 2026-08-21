# Correcoes v0.7.1 - Atualizador GitHub

Esta versao corrige o comportamento da aba **Atualizacoes**.

## Problema identificado

O atualizador anterior consultava simultaneamente a ultima Release e o `VERSAO.txt` e tratava falhas esperadas do GitHub como erro da aplicacao. Isso fazia a tela parecer quebrada quando:

- o repositorio ainda nao estava publico/acessivel;
- ainda nao existia uma Release;
- o `Setup.exe` ainda estava sendo publicado;
- a maquina estava temporariamente sem internet;
- a API anonima do GitHub atingia limite temporario.

## Novo fluxo

O comportamento agora segue o mesmo principio do Monitor Carat + PDV:

1. a **GitHub Release** e a fonte oficial para atualizacao instalavel;
2. o `VERSAO.txt` so e consultado como contingencia quando a Release nao pode ser lida;
3. uma atualizacao so fica habilitada se a Release tiver os dois arquivos:
   - `AutomacaoAgilize-Setup.exe`
   - `AutomacaoAgilize-Setup.exe.sha256`
4. estados esperados do GitHub nao geram popup vermelho nem bloqueiam a Automacao Agilize.

## Estados da interface

- `updated`: sistema alinhado com a ultima Release.
- `update_available`: nova Release completa e pronta para instalar.
- `release_pending`: versao nova detectada, mas a Release ainda nao esta completa.
- `repository_unavailable`: repositorio nao encontrado ou nao acessivel publicamente.
- `offline`: sem acesso ao canal de atualizacao.
- `rate_limited`: limite temporario do GitHub.
- `check_failed`: falha inesperada que merece diagnostico.

Somente `update_available` exibe banner na tela principal e habilita **Atualizar agora**.

## Importante sobre o repositorio

O cliente instalado nao deve depender das credenciais Git da maquina do usuario. Para o modelo atual, o repositorio/Release usado como canal de distribuicao precisa estar acessivel aos computadores que vao consultar e baixar a atualizacao.

Repositorio configurado:

`JoseLuiz095/automacao-agilize`

Use `FERRAMENTAS/06_CONFIGURAR_GITHUB.bat` para validar o remote de desenvolvimento e `FERRAMENTAS/08_TESTAR_ATUALIZACAO.bat` para diagnosticar o atualizador.
