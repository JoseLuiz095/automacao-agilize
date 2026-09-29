# Correcoes v0.8.9 - destino do lancamento independente do historico

## Problema

A selecao `Doc. - Contas a pagar` era usada apenas para definir a ordem da pesquisa historica. Depois de localizar observacao/aprovador, o fluxo final chamava sempre o preenchimento de NFS-E (`/nfs`).

Isso fazia uma Nota de Debito da LOL ser preparada em `Notas NFS-E` mesmo quando:

- o usuario escolhia `Doc. - Contas a pagar`; ou
- o modo Automatico classificava o PDF como documento de contas a pagar.

## Regra nova

A partir da v0.8.9 existem dois conceitos separados:

1. **Historico**: pode consultar `Doc. - Contas a pagar` e `Notas NFS-E` para localizar observacao/aprovador.
2. **Destino**: e definido pela escolha do usuario ou pelo tipo detectado nos PDFs e nao muda por causa do local onde o historico foi encontrado.

Exemplo:

`Doc. - Contas a pagar -> historico encontrado em NFS-E -> destino continua Doc. - Contas a pagar`.

## Automatico para LOL

Notas de Debito da LOL (`09.267.506/0001-36`) sao direcionadas a `Doc. - Contas a pagar` no modo Automatico. O parser ja reconhece `NOTA DE DEBITO`; o CNPJ foi adicionado como segunda protecao contra mudancas de layout.

Para o exemplo atual:

- Fatura/Documento: 213847
- Fornecedor: LOL SERVICOS DE INTERNET LTDA
- CNPJ: 09.267.506/0001-36
- Empresa: LEAO COMERCIO DE MOVEIS LTDA
- Valor: R$ 200,00
- Vencimento: 15/09/2026

O destino e `Doc. - Contas a pagar`.

## Protecao contra lancamento na area errada

A automacao nao usa mais NFS-E como fallback de criacao quando o destino e `Doc. - Contas a pagar`.

Em `/documentos`, ela tenta:

1. localizar um documento atual ja existente pelo numero/fatura;
2. complementar o registro se um formulario reconhecido for aberto;
3. localizar um comando de novo documento e preencher os campos mapeaveis.

Se o layout atual de `/documentos` nao corresponder aos seletores conhecidos, a pagina correta permanece aberta e o processo e interrompido com mensagem de diagnostico. **Nao sera criada uma NFS-E por engano.**

Para automatizar integralmente um layout novo de `/documentos`, o HAR ideal e pequeno: abrir `Doc. - Contas a pagar`, clicar em novo/enviar documento e aguardar o formulario aparecer, sem efetuar o envio.
