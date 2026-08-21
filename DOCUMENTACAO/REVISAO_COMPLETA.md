# Revisão completa - v0.6.0

A revisão foi feita tomando como referência a organização e o fluxo do projeto **Monitor Carat + PDV** e comparando com a versão anterior da Automação Agilize.

## Problemas encontrados na estrutura anterior

- arquivos Python, BATs, instalador e configuração de build estavam todos na raiz;
- o ambiente de build ficava junto do projeto, aumentando ruído e risco de compartilhar arquivos desnecessários;
- o executável não possuía ícone próprio configurado no PyInstaller;
- a janela Tkinter não aplicava um ícone próprio;
- não havia `AppUserModelID` fixo para associação consistente do ícone na barra de tarefas;
- o instalador criava atalhos sem `AppUserModelID` explícito;
- o atualizador iniciava o instalador antes do processo atual encerrar, criando risco de conflito com a substituição do EXE;
- não havia validação SHA-256 da atualização;
- dados locais ficavam pouco organizados dentro de `%LOCALAPPDATA%\AutomacaoAgilize`;
- o scrollbar padrão do `ttk` era visualmente largo e destoava da interface;
- ao adicionar um PDF e depois outro, o segundo drop podia substituir a seleção anterior;
- com documento único, a mesma fonte podia ser comparada contra ela mesma e gerar aviso falso de divergência.

## Melhorias implementadas

### Projeto

Nova divisão:

- `app/` - código da aplicação;
- `assets/` - recursos visuais;
- `build/` - PyInstaller e dependências;
- `installer/` - Inno Setup e saída final;
- `FERRAMENTAS/` - scripts de manutenção;
- `DOCUMENTACAO/` - manuais e histórico;
- `tests/` - validações;
- `.github/workflows/` - geração de Releases.

### Ícone e Windows

O ícone `assets/automacao-agilize.ico` agora é usado pelo:

- PyInstaller no `AutomacaoAgilize.exe`;
- Tkinter na janela principal;
- Inno Setup no instalador;
- atalho da Área de Trabalho;
- atalho do Menu Iniciar.

Também foi adicionado `JoseLuiz.AutomacaoAgilize` como `AppUserModelID`, tanto na aplicação quanto nos atalhos do Inno Setup.

### Dados persistentes

Agora:

```text
%LOCALAPPDATA%\AutomacaoAgilize\
├─ config\settings.json
├─ logs\
├─ browser-profiles\
├─ updates\
├─ cache\
└─ temp\
```

A versão nova migra automaticamente `settings.json` e o perfil Edge antigo quando encontrados.

### Atualizador

- consulta Releases do GitHub;
- procura `AutomacaoAgilize-Setup.exe`;
- usa `AutomacaoAgilize-Setup.exe.sha256` quando publicado;
- valida SHA-256 antes de executar;
- espera o processo atual encerrar;
- instala silenciosamente;
- reabre a aplicação após uma atualização bem-sucedida.

### Interface

- layout mais compacto para notebooks;
- conteúdo continua rolável quando necessário;
- scrollbar próprio de 8 px, sem setas;
- nomes grandes de arquivo são compactados visualmente;
- PDFs podem ser adicionados em duas etapas;
- cada PDF pode ser removido individualmente;
- a tela principal mantém somente ações essenciais;
- detalhes técnicos continuam escondidos por padrão.

### Robustez

- instância única no Windows para evitar dois processos usando o mesmo perfil do navegador;
- logs de inicialização persistentes;
- build local em `%LOCALAPPDATA%\AutomacaoAgilizeBuild`;
- BAT do instalador em ASCII/CRLF para evitar problemas do `cmd.exe` com acentuação;
- workflow GitHub Actions publica Setup + SHA-256;
- `VERSAO.txt` passa a ser a fonte única da versão.

## Sobre a barra de tarefas

A versão 0.6.0 corrige o **ícone exibido enquanto a aplicação está aberta** e a identidade usada pelo Windows para os atalhos. Fixar automaticamente um aplicativo na barra de tarefas é controlado pelo próprio Windows; o usuário pode usar **Fixar na barra de tarefas** no atalho ou no ícone em execução.
