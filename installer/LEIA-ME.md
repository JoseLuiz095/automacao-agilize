# Instalador Windows - Automação Agilize

O usuário final deve receber somente `AutomacaoAgilize-Setup.exe`.

## Build local

Execute `installer\GERAR_INSTALADOR_EXE.bat`.

O instalador final será criado em `installer\output\` junto com o SHA-256.

## Instalação

Código instalado por usuário:

`%LOCALAPPDATA%\Programs\AutomacaoAgilize`

Dados persistentes, credenciais, perfis do navegador e logs:

`%LOCALAPPDATA%\AutomacaoAgilize`

Atualizar ou reinstalar não apaga os dados persistentes.
