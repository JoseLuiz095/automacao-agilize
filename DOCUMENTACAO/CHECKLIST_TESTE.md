# Checklist de teste da v0.6.2

## Instalação

- executar `installer\GERAR_INSTALADOR_EXE.bat`;
- confirmar `installer\output\AutomacaoAgilize-Setup.exe`;
- instalar o Setup;
- confirmar atalho **Automação Agilize** no Menu Iniciar;
- se marcada a opção, confirmar atalho na Área de Trabalho;
- abrir a aplicação e confirmar o ícone verde **A** na janela e na barra de tarefas.

## Interface

- reduzir a altura da janela e confirmar que o scrollbar fino aparece;
- testar roda do mouse e arraste do thumb;
- adicionar um PDF sozinho;
- adicionar um PDF e depois o segundo em outro drag/drop;
- remover apenas um PDF pelo botão `×`;
- confirmar que nomes longos não estouram a largura da tela.

## Automação

- testar um documento único combinado;
- testar NFS-e + recibo/boleto;
- conferir CNPJ do fornecedor;
- conferir nome retornado pelo CNPJ;
- conferir vencimento;
- conferir RATEIO recuperado do mês anterior;
- confirmar que todos os PDFs adicionados estão no Anexo;
- confirmar que a automação não envia a nota.

## Atualização

- publicar uma Release superior à instalada;
- confirmar detecção na aba Atualizações;
- baixar e instalar;
- confirmar SHA-256;
- confirmar fechamento, atualização e reabertura do aplicativo;
- confirmar preservação de credenciais e perfil do navegador.
