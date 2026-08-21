# Estrutura do projeto

```text
AutomacaoAgilize/
├─ app/                 código Python da aplicação
├─ assets/              ícone e recursos visuais
├─ build/               PyInstaller e dependências de build
├─ installer/           Inno Setup e saída do Setup.exe
├─ FERRAMENTAS/         manutenção/desenvolvimento
├─ DOCUMENTACAO/        documentação do projeto
├─ tests/               validações sem dados reais de clientes
├─ .github/workflows/   geração automática de Releases
├─ VERSAO.txt           fonte única da versão
└─ README.md
```

## Instalação do usuário final

O instalador grava o aplicativo em:

`%LOCALAPPDATA%\Programs\AutomacaoAgilize`

Dados que devem sobreviver a atualizações ficam separados em:

```text
%LOCALAPPDATA%\AutomacaoAgilize\
├─ config\
├─ logs\
├─ browser-profiles\
├─ updates\
├─ cache\
└─ temp\
```

Essa separação segue o mesmo princípio do projeto Monitor Carat + PDV: código instalado de um lado e dados locais persistentes do outro.
