from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from batch import agrupar_documentos
from pdf_reader import (
    _achar_fatura_boleto,
    _achar_nota_fiscal_referenciada_boleto,
    _achar_valor_pagamento,
)


BOLETO_47736 = """
RECIBO DO PAGADOR
FINNET S/A - TECNOLOGIA E INSTITUICAO DE PAGAMENTO
05.607.266/0001-10
PAGADOR
LCR COMERCIO DE MOVEIS LTDA
09.081.947/0001-49
NOSSO NUMERO
02343301
VENCIMENTO
28/08/2026
VALOR A PAGAR
R$ 751,40
NOTA FISCAL
47736
FATURA
23433
"""

NOTA_47736 = """
PREFEITURA MUNICIPAL DE BARUERI
NOTA FISCAL ELETRONICA DE SERVICOS - NFE
Numero da Nota
0047736
Data Emissao Hora Emissao
21/08/2026 06:50
Prestador de Servicos
FINNET S/A - TECNOLOGIA E INSTITUICAO DE PAGAMENTO
CNPJ/CPF 05.607.266/0001-10
Nome Tomador de Servicos CPF/CNPJ
LCR COMERCIO DE MOVEIS LTDA 09.081.947/0001-49
VALOR TOTAL DA NOTA 751,40
Data de Vencimento: 28/08/2026
Meio de Pagamento: Boleto Bancario Bradesco
"""

BOLETO_47737 = BOLETO_47736.replace("02343301", "02343401").replace("751,40", "3.001,78").replace("47736", "47737").replace("23433", "23434")
NOTA_47737 = NOTA_47736.replace("0047736", "0047737").replace("751,40", "3.001,78")


def _pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(36, 36, 560, 800), text, fontsize=9)
    doc.save(path)
    doc.close()


def main() -> None:
    assert _achar_nota_fiscal_referenciada_boleto(BOLETO_47736) == "47736"
    assert _achar_fatura_boleto(BOLETO_47736) == "23433"
    assert _achar_valor_pagamento(BOLETO_47736) == "751,40"
    assert _achar_valor_pagamento(BOLETO_47737) == "3.001,78"

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        files = [
            base / "boleto_47736.pdf",
            base / "nota_47736.pdf",
            base / "boleto_47737.pdf",
            base / "nota_47737.pdf",
        ]
        for path, text in zip(files, [BOLETO_47736, NOTA_47736, BOLETO_47737, NOTA_47737]):
            _pdf(path, text)
        grupos = agrupar_documentos(files)
        assert len(grupos) == 2, [(g.numero, [p.name for p in g.paths]) for g in grupos]
        por_num = {g.numero: g for g in grupos}
        assert set(por_num) == {"47736", "47737"}
        assert len(por_num["47736"].documentos) == 2
        assert len(por_num["47737"].documentos) == 2
        assert por_num["47736"].dados and por_num["47736"].dados.valor == "751,40"
        assert por_num["47737"].dados and por_num["47737"].dados.valor == "3.001,78"

    print("[OK] FINNET: nota + boleto pareados pelo numero da nota fiscal")
    print("[OK] valores FINNET extraidos pelo campo VALOR A PAGAR")


if __name__ == "__main__":
    main()
