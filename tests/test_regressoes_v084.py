from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from batch import agrupar_documentos  # noqa: E402
from pdf_reader import (  # noqa: E402
    _achar_emissao,
    _achar_numero_documento_pagamento,
    _achar_numero_nota,
    _achar_numero_rps,
    _achar_provider_cnpj,
    _achar_referencia_periodo,
    _achar_valor,
    _achar_vencimento,
    _achar_empresa_interna,
    cnpj_valido,
    extrair_dados,
)

STARTING_NOTA = """
Razão Social: STARTING HUB DE INOVACAO LTDA
Endereço: Avenida Comendador Rafael, 2199, ANDAR 4 - COLINA
Inscrição Municipal: 0039894 - CPF/CNPJ: 46.882.111/0001-70
Nº da Nota Fiscal
Data Fato Gerador
21/08/2026
NFSE
Serie RPS
Nome Fantasia: STARTING HUB
PRESTADOR
21/08/2026 15:13:11
Emitido em
Razão Social: LCR COMERCIO DE MOVEIS LTDA
CPF/CNPJ: 09.081.947/0001-49
TOMADOR
CNPJ: 27.167.410/0001-88
Codigo de Verificação para Autenticação: rps_2670
PREFEITURA MUNICIPAL DE LINHARES
NOTA FISCAL DE SERVIÇOS ELETRÔNICA - NFSe
2670
Número RPS
2657
SERVIÇO NACIONAL
DISCRIMINAÇÃO DOS SERVIÇOS
SERVICO DE APOIO ADMINISTRATIVO - Qtde 1 x Valor Unit. R$ 1.621,00 = Total R$ 1.621,00.
OBSERVAÇÃO
REFERENTE LICENCA DE USO DE SOFTWARE
Ref. Ago/2026
Chave de acesso Ambiente de Dados Nacional: 32032051246882111000170260000000265726080010212319
"""

STARTING_BOLETO = """
Beneficiário
Vencimento
Valor do Documento
Nome do pagador
Número do Documento
Dados do Pagador
Local de pagamento
Beneficiário
Data do documento
Pagador
Ficha de compensação
N. documento
Espécie
Aceite
Data processamento
STARTING HUB DE INOVACAO LTDA
05/09/2026
1.621,00
21/08/2026
3007/3967387/22889
2709-0
LCR COMERCIO DE MOVEIS LTDA
2657
D. PEDRO II, 615, 615
Eunapolis
BA
45820080
PAGAVEL PREFERENCIALMENTE NO SICOOB
STARTING HUB DE INOVACAO LTDA
21/08/2026
1
0,00
2657
DS
N
21/08/2026
2709-0
05/09/2026
3007/3967387/22889
1.621,00
LCR COMERCIO DE MOVEIS LTDA
09081947000149
D. PEDRO II, 615, 615
45820080
Eunapolis - BA
75691.30078 01396.738708 00270.900012 9 15600000162100
756
COOPERATIVA CONTRATANTE 3007 SICOOB CONEXAO
46882111000170
46882111000170
RUI BARBOSA 1078 SALA 05
Linhares - ES
29900072
"""

STARTING_DEMONSTRATIVO = """
DEMONSTRATIVO DA NOTA FISCAL DE SERVIÇO
Emitida em Linhares (ES)
Este documento não tem valor fiscal
Número da NFS-e
2657
Data de Emissão
21/08/2026 15:06:55
Competência
08/2026
Código de Verificação
rps_2670
Dados do Prestador
Razão Social
STARTING HUB DE INOVACAO LTDA
CNPJ
46.882.111/0001-70
Dados do Tomador
Razão Social
LCR COMERCIO DE MOVEIS LTDA
CNPJ
09.081.947/0001-49
Detalhamento dos Serviços
SERVICO DE APOIO ADMINISTRATIVO - Qtde 1 x Valor Unit. R$ 1.621,00 = Total R$ 1.621,00.
Valor Total dos Serviços R$
1.621,00
Valor líquido da NFS-e R$ 1.621,00
"""


def _pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(36, 36, 560, 800), text, fontsize=7)
    doc.save(path)
    doc.close()


def test_parsers_starting() -> None:
    assert _achar_numero_nota(STARTING_NOTA) == "2657"
    assert _achar_numero_rps(STARTING_NOTA) == "2670"
    assert _achar_emissao(STARTING_NOTA) == "2026-08-21"
    assert _achar_valor(STARTING_NOTA) == "1.621,00"
    assert _achar_referencia_periodo(STARTING_NOTA) == "Agosto/2026"

    assert _achar_numero_documento_pagamento(STARTING_BOLETO) == "2657"
    assert _achar_vencimento(STARTING_BOLETO) == "2026-09-05"

    company_cnpj, _, _ = _achar_empresa_interna(STARTING_BOLETO)
    assert company_cnpj == "09.081.947/0001-49"
    assert _achar_provider_cnpj(STARTING_BOLETO, company_cnpj) == "46.882.111/0001-70"
    assert cnpj_valido("46.882.111/0001-70")
    assert not cnpj_valido("15.600.000/1621-00")


def test_grupo_com_demonstrativo_nao_enviado() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        nota = base / "nfse_2657.pdf"
        boleto = base / "boleto_2657.pdf"
        demo = base / "demonstrativo_2657.pdf"
        _pdf(nota, STARTING_NOTA)
        _pdf(boleto, STARTING_BOLETO)
        _pdf(demo, STARTING_DEMONSTRATIVO)

        grupos = agrupar_documentos([demo, boleto, nota])
        assert len(grupos) == 1
        grupo = grupos[0]
        assert grupo.numero == "2657"
        assert len(grupo.documentos) == 2
        assert len(grupo.documentos_referencia) == 1
        assert {p.name for p in grupo.paths} == {"nfse_2657.pdf", "boleto_2657.pdf"}
        assert "demonstrativo_2657.pdf" not in {p.name for p in grupo.paths}
        assert grupo.documentos_referencia[0].path.name == "demonstrativo_2657.pdf"
        assert grupo.dados is not None
        assert grupo.dados.numero == "2657"
        assert grupo.dados.provider_cnpj == "46.882.111/0001-70"
        assert grupo.dados.company_cnpj == "09.081.947/0001-49"
        assert grupo.dados.valor == "1.621,00"
        assert grupo.dados.vencimento == "2026-09-05"
        assert grupo.dados.banco == "Sicoob"


def test_amostras_reais_se_disponiveis() -> None:
    nota = Path("/mnt/data/NFSe2657_46882111000170.pdf")
    boleto = Path("/mnt/data/starting_vencto_05_09_2026_doc_2657_bol_2709_cli_09081947000149_001.pdf")
    demo = Path("/mnt/data/demonstrativo_nfse_2657.pdf")
    if not (nota.exists() and boleto.exists() and demo.exists()):
        return

    grupos = agrupar_documentos([demo, nota, boleto])
    assert len(grupos) == 1
    grupo = grupos[0]
    assert grupo.numero == "2657"
    assert len(grupo.documentos) == 2
    assert len(grupo.documentos_referencia) == 1
    assert demo not in grupo.paths

    dados, _, _ = extrair_dados(nota, boleto)
    assert dados.numero == "2657"
    assert dados.provider_cnpj == "46.882.111/0001-70"
    assert dados.provider_name == "STARTING HUB DE INOVACAO LTDA"
    assert dados.company_cnpj == "09.081.947/0001-49"
    assert dados.valor == "1.621,00"
    assert dados.emissao == "2026-08-21"
    assert dados.vencimento == "2026-09-05"
    assert dados.pagamento_numero_documento == "2657"
    assert dados.nosso_numero == "2709-0"
    assert dados.banco == "Sicoob"
    assert dados.referencia_periodo == "Agosto/2026"


def main() -> int:
    test_parsers_starting()
    test_grupo_com_demonstrativo_nao_enviado()
    test_amostras_reais_se_disponiveis()
    print("[OK] v0.8.4 - Starting Hub/Sicoob pareado em 1 lancamento")
    print("[OK] v0.8.4 - demonstrativo sem valor fiscal nao e anexado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
