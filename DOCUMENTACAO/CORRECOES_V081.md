# Automação Agilize v0.8.1 - Atualização automática corrigida

## Problema reproduzido

A aplicação instalada estava em `v0.7.3` e o `VERSAO.txt` do GitHub já estava em `v0.8.0`, porém ainda não existia uma GitHub Release contendo:

- `AutomacaoAgilize-Setup.exe`
- `AutomacaoAgilize-Setup.exe.sha256`

Nesse intervalo o sistema conseguia detectar o código novo, mas o botão de atualização permanecia inutilizável.

## Correção 1 - Release passa a ser criada automaticamente

O workflow `.github/workflows/release-installer.yml` agora é executado quando `VERSAO.txt` muda na branch `main`.

O pipeline:

1. lê e valida `VERSAO.txt`;
2. executa todos os testes `test_regressoes_v*.py`;
3. gera o executável com PyInstaller;
4. compila `AutomacaoAgilize-Setup.exe` com Inno Setup;
5. calcula SHA-256;
6. cria automaticamente a tag/Release `v<versão>`;
7. publica `AutomacaoAgilize-Setup.exe` e `.sha256`;
8. confirma que ambos os assets realmente estão na Release.

Não é mais necessário criar a tag manualmente.

## Correção 2 - botão Aguardar instalador

Quando `VERSAO.txt` já aponta uma versão nova, mas o GitHub Actions ainda está construindo a Release, a aplicação exibe:

`Aguardar instalador`

Ao clicar, a Automação Agilize consulta a Release automaticamente a cada poucos segundos por até 10 minutos. Assim que Setup + SHA-256 aparecem, o fluxo continua sozinho:

`aguardar -> baixar -> validar SHA-256 -> fechar app -> instalar -> reabrir`

## Correção 3 - Release antiga não mascara VERSAO.txt novo

Antes, se existisse uma Release antiga, ela podia ser considerada autoritativa e o sistema não verificava que `VERSAO.txt` já estava à frente.

Agora, quando a Release não é mais nova que a instalação, o updater também compara `VERSAO.txt`. Isso permite mostrar corretamente que uma publicação está em andamento.

## Correção 4 - Git Credential Manager

Para repositórios privados no computador do desenvolvedor, o updater tenta reutilizar, somente em memória, a credencial já armazenada pelo Git Credential Manager.

A credencial:

- não é gravada no `settings.json`;
- não é escrita em logs;
- não é incorporada ao executável.

Computadores sem credencial continuam usando o canal público/anônimo normalmente.

## Publicação recomendada

Para publicar uma nova versão, use:

```bat
FERRAMENTAS\07_PUBLICAR_VERSAO.bat 0.8.2
```

O script altera `VERSAO.txt`, cria o commit e envia `main`. O restante é feito pelo GitHub Actions.

## Migração da versão antiga

A versão já instalada antes desta correção não conhece o novo fluxo de espera nem o reaproveitamento automático do Git Credential Manager para baixar uma Release privada.

Depois que a Release v0.8.1 existir, se a instalação antiga ainda não conseguir atualizar por dentro da aplicação, execute uma única vez:

```bat
FERRAMENTAS\12_MIGRAR_ATUALIZADOR_ANTIGO.bat
```

Esse utilitário usa a credencial já existente no Git Credential Manager, baixa a Release oficial, valida SHA-256 e executa o Setup. Depois da migração para v0.8.1, as próximas atualizações passam a ser tratadas pelo próprio aplicativo.
