# Build e instalador

## Build local

Execute:

`installer\GERAR_INSTALADOR_EXE.bat`

O BAT mantém o ambiente de build fora do projeto em:

`%LOCALAPPDATA%\AutomacaoAgilizeBuild\venv`

Isso evita `.venv`, `dist` e dependências misturadas ao código fonte.

Saída:

`installer\output\AutomacaoAgilize-Setup.exe`

## Ícones

O mesmo ícone é aplicado em quatro pontos:

1. executável PyInstaller;
2. janela Tkinter;
3. atalho da Área de Trabalho/Menu Iniciar;
4. instalador Inno Setup.

O processo também define um `AppUserModelID` fixo para o Windows associar corretamente o ícone à janela na barra de tarefas.


## Correção 0.6.1 - caminho do PyInstaller

O arquivo `build/AutomacaoAgilize.spec` usa `SPECPATH` como a pasta onde o `.spec` está localizado.
Como o `.spec` está em `build/`, a raiz do projeto é exatamente o diretório pai de `SPECPATH`.
A versão 0.6.0 subia dois níveis e procurava `app/launcher.py` fora da pasta do projeto.
A 0.6.1 corrige essa resolução e valida os caminhos antes de iniciar o PyInstaller.
