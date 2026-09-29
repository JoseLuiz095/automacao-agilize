# Correções v0.9.5 — lotes grandes e downloads do Zimbra

## 1. ERR_INSUFFICIENT_RESOURCES em lotes grandes

A fila anterior mantinha duas abas Chromium por lançamento (formulário do Agilize + PDF de conferência) e continuava abrindo novas abas sem limite. Em lotes de 20 notas isso podia ultrapassar os recursos disponíveis do Edge/Chrome e gerar:

`net::ERR_INSUFFICIENT_RESOURCES`

A v0.9.5 passa a trabalhar com um limite seguro de 6 lançamentos preparados simultaneamente (configurável por `AUTOMACAO_AGILIZE_MAX_ABERTOS`, entre 2 e 10).

Quando o limite é atingido, a fila pausa sem erro. Assim que um formulário é enviado/cancelado ou sua aba é fechada, as abas daquele lançamento são liberadas e o próximo item da fila continua automaticamente.

Também foi incluído retry específico para `ERR_INSUFFICIENT_RESOURCES` e o PDF de conferência deixou de derrubar o lançamento inteiro caso apenas a aba do PDF não consiga abrir.

## 2. Nova aba E-mail / Downloads

Foi adicionada uma aba antes de Lançamento para baixar anexos PDF do Zimbra por IMAP.

Filtros:
- conta de e-mail;
- remetente;
- data inicial e final;
- pasta IMAP (padrão INBOX);
- pasta local de destino.

O servidor IMAP pode ser informado manualmente ou descoberto automaticamente por nomes comuns do domínio (`imap`, `mail`, `zimbra`, `webmail`).

As credenciais são armazenadas via DPAPI no Windows, no mesmo padrão de segurança já usado pelo acesso do Agilize. Também é possível usar diretamente as mesmas credenciais do Agilize.

## 3. hCaptcha / portal NFS-e

A automação NÃO tenta resolver ou contornar hCaptcha.

Quando um e-mail contém link para portal/consulta NFS-e, o link é listado em `Pendências manuais`. O usuário pode abrir o item no navegador, concluir o captcha e efetuar o download manualmente. A guia permanece aberta.

Depois, o botão `Importar PDFs baixados manualmente` procura PDFs novos na pasta Downloads desde o início da pesquisa, copia-os para a pasta de destino e adiciona-os à fila do Agilize.

## 4. Integração com a fila

Os PDFs anexos baixados do Zimbra podem ser adicionados automaticamente à fila de lançamentos. A associação nota/boleto continua sendo feita pelo mesmo motor de pareamento já existente.
