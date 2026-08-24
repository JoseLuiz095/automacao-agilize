# Correções v0.8.3 - atualizador simplificado

## Diagnóstico do problema

O aplicativo encontrava `VERSAO.txt` com versão nova e, em seguida, ficava aguardando o GitHub Actions criar uma Release. Enquanto a Release não existia, `releases/latest` retornava HTTP 404. Isso gerava uma experiência confusa e podia permanecer aguardando indefinidamente quando o workflow não executava ou falhava.

## Nova regra

A partir da v0.8.3 existe **uma única fonte de verdade** para atualização:

**a última GitHub Release publicada.**

O aplicativo não consulta mais `VERSAO.txt` para decidir se existe atualização e não monitora GitHub Actions.

## Publicação

Use:

```bat
FERRAMENTAS\07_PUBLICAR_VERSAO.bat 0.8.3
```

O script:

1. grava a versão local;
2. tenta sincronizar o código se a pasta já for um clone Git válido;
3. gera o instalador localmente;
4. autentica no GitHub CLI, se necessário;
5. cria ou atualiza a Release `vX.Y.Z`;
6. envia `AutomacaoAgilize-Setup.exe`;
7. envia `AutomacaoAgilize-Setup.exe.sha256`;
8. confirma que os dois arquivos existem na Release.

A Release só é criada depois que o Setup já foi gerado localmente.

## Comportamento do aplicativo

- Sem Release: informa apenas que ainda não existe versão publicada.
- Release igual à instalada: sistema atualizado.
- Release mais nova + Setup + SHA: habilita **Atualizar agora**.
- Release mais nova sem algum asset: informa **Release incompleta** e pede republicação.
- Não existe mais botão **Aguardar instalador**.
- Não existe mais polling do GitHub Actions.

## Transição de versões antigas

Versões como v0.8.1 já consultam GitHub Releases. Portanto, assim que uma Release v0.8.3 completa for publicada, a versão antiga deve conseguir detectar o instalador e migrar para o novo atualizador.
