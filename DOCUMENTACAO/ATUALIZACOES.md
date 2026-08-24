# Atualizações - Automação Agilize v0.8.3+

## Arquitetura

O atualizador consulta somente:

`https://api.github.com/repos/JoseLuiz095/automacao-agilize/releases/latest`

A última Release é a fonte oficial da versão.

## Assets obrigatórios

Cada Release precisa conter:

- `AutomacaoAgilize-Setup.exe`
- `AutomacaoAgilize-Setup.exe.sha256`

O aplicativo somente habilita **Atualizar agora** quando os dois arquivos estão presentes.

## Publicação recomendada

No computador de desenvolvimento execute:

```bat
FERRAMENTAS\07_PUBLICAR_VERSAO.bat 0.8.3
```

O GitHub CLI pode pedir autenticação no navegador apenas na primeira utilização.

## Por que não usar GitHub Actions neste fluxo

O build automático introduzia um estado intermediário: o código já informava uma versão nova, mas o instalador ainda não existia. O usuário via 404 e precisava aguardar um workflow externo.

Na v0.8.3 o instalador é gerado antes e a Release é publicada já completa. Isso reduz o número de estados e pontos de falha.
