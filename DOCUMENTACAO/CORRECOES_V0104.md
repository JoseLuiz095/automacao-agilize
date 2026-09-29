# Automacao Agilize v0.10.4 - Pre-lancamento NFS-e

## Base e escopo

Correcao localizada nos arquivos de automacao publicados no commit
be27783a24d6483700fcac37a91de31b108f7535, cuja VERSAO.txt informa 0.10.3.
Os blobs de app/agilize.py, app/agilize_batch.py e app/version.py foram
conferidos com os arquivos utilizados nesta correcao. A instalacao do pacote
confere o conteudo anterior e preserva arquivos que nao fazem parte do ajuste.
Nao foram feitas alteracoes remotas no GitHub nesta entrega.

## Causa identificada

A sessao sequencial so chamava _localizar_registro_existente quando o destino
ja era nfse. Ao resolver documentos, ignorava o pre-lancamento NFS-e e seguia
para um formulario novo em Contas a pagar. O cache ainda armazenava None,
impedindo novas consultas historicas nas repeticoes da mesma referencia.
O metodo _aplicar_periodo_lista preenchia os campos sem confirmar os valores
e ignorava erros. A selecao textual de Fornecedor tambem podia escolher
Documento fornecedor ao receber uma razao social.

## Alteracoes

- Verificacao de existencia em Notas NFS-E antes de preparar qualquer destino.
- Se houver correspondencia completa, reaproveita a NFS-e existente em vez de
  criar um documento em Contas a pagar. Sem correspondencia, preserva o destino.
- A verificacao inicial e a busca por fornecedor cobrem o mes da emissao mais
  tres meses anteriores completos; nunca aceitam menos de dois meses anteriores.
  Para a nota emitida em 21/09/2026: 01/06/2026 a 30/09/2026.
- Mantida a tentativa ampla pelo numero se a primeira pesquisa nao retornar.
- Texto e datas sao preenchidos, aguardados e lidos novamente na tela. Se a
  interface restaurar datas, o intervalo e reaplicado, no maximo tres tentativas.
  Datas/consulta inconclusivas interrompem o fluxo, em vez de autorizar cadastro.
- A busca pelo nome nao escolhe o filtro de CNPJ por uma coincidencia textual.
- Correspondencia entre areas exige numero exato ou prefixado, empresa/filial,
  CNPJ do fornecedor, valor e emissao. Sufixo sozinho nao e suficiente.
- Mais de um pre-cadastro prefixado compativel exige conferencia manual.
- Resultado historico vazio nao fica em cache. O cache positivo permanece,
  mas nunca substitui a verificacao atual de existencia.
- Se o registro passar para Efetuada/Aguardando Aprovacao durante a consulta,
  nao volta a preencher ou anexar documentos.
- Mensagem de historico informa somente as areas que realmente pesquisou.
- Pesquisa de documentos existentes confirma datas e nao cria outro documento
  quando a consulta falha ou o formulario existente nao abre.
- Versao efetiva e versao de contingencia atualizadas para 0.10.4.

## Regras preservadas

Envio final manual; fila sequencial; preenchimento de observacao/aprovador e
anexos; classificacao dos documentos quando nao ha pre-cadastro correspondente;
historico de NFS-e apenas Efetuada e nos meses anteriores (nao confundir esta
janela com a pesquisa da propria nota, que obrigatoriamente inclui o mes atual).
O BAT de publicacao existente nao foi substituido. Nao ha migration SQL.

## Validacao e limites

Foram executadas a validacao estrutural/imports, as regressoes existentes,
20 novos testes de datas/identidade/fila/cache/bloqueio e um teste em Chromium
com pagina local controlada. Nesse teste o campo de data foi restaurado pela
pagina e reaplicado pelo bot; a busca por nome encontrou 2600000002721 e abriu
o modal importado, sem clicar em novo lancamento.

O teste local nao equivale a homologacao no portal real. Nao houve login,
envio de notas, alteracao de dados do Agilize, build EXE no Windows ou push.
Validar no ambiente do usuario antes de publicar a Release.
