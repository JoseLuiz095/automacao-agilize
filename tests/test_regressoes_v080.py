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
    _achar_numero_nota,
    _achar_numero_rps,
    _achar_numero_documento_pagamento,
    _achar_valor,
    _achar_valor_pagamento,
)

AUDITOR_NOTA = """
DANFSe v2.0
Documento Auxiliar da NFS-e
NÚMERO DA NFS-e
2605
PRESTADOR / FORNECEDOR CNPJ / CPF / NIF
32.401.507/0001-43
TOMADOR / ADQUIRENTE CNPJ / CPF / NIF
23.284.146/0001-01
VALOR DA OPERAÇÃO / SERVIÇO
R$ 778,58
"""

AUDITOR_RECIBO = """
RECIBO DA NOTA FISCAL DE SERVIÇOS ELETRÔNICA
Nº NFS-e
1ª VIA
DATA EMISSÃO
002605
17/08/2026
WI COMERCIO ATACADISTA DE MOVEIS LTDA
23.284.146/0001-01
AS AUDITORIA SISTEMAS E REPRESENTAÇÕES LTDA EPP
CNPJ: 32.401.507/0001-43
FICHA DE COMPENSAÇÃO
Número do Documento
76197/1
Vencimento
01/09/2026
R$778,58
"""

LOL_NOTA = """
NOTA DE DÉBITO
LCR COM. DE MOVEIS LTDA - Stª Teresa - 09.081.947/0007-34
LOL SERVIÇOS DE INTERNET LTDA
09.267.506/0001-36
INFORMAÇÕES DA COBRANÇA
Fatura: 208938 Cod. Comp: 330 Emissão: 11/05/2026
Total: R$ 200,00
"""

LOL_BOLETO = """
RECIBO DO PAGADOR
FICHA DE COMPENSAÇÃO
LOL SERVIÇOS DE INTERNET LTDA
09.267.506/0001-36
LCR COM. DE MOVEIS LTDA - Stª Teresa
Nº do documento
208938
Vencimento
15/05/2026
Valor do documento
200,00
"""

SKYTEF_NOTA = """
991482
86UIRCGI
Numero da Nota
Data e Hora da Emissão
Código de Verificação
15/06/2026 16:26:00
NOTA FISCAL ELETRONICA DE SERVIÇOS - NFS-e
RPS N° 991.483 Série 1, emitido em 15/06/2026
CPF/CNPJ: 04.988.631/0001-11
SKYTEF SOLUÇÕES EM CAPTURA DE TRANSAÇÕES LTDA
TOMADOR DE SERVIÇOS
LCR COMERCIO DE MOVEIS LTDA
C.P.F. / C.N.P.J. 09.081.947/0005-72
Valor liquido a ser pago: 269,94
Data de vencimento: 01/07/2026
VALOR TOTAL DOS SERVIÇOS = 269,94
"""

SKYTEF_BOLETO = """
RECIBO DO PAGADOR
FICHA DE COMPENSAÇÃO
Beneficiário
SKYTEF SOLUÇÕES EM CAPTURA DE TRANSAÇÕES
04.988.631/0001-11
Pagador
LCR COMERCIO DE MOVEIS LTDA
CNPJ 09.081.947/0005-72
Número do Documento
991483-01
Vencimento
01/07/2026
(=) Valor do Documento em R$
269,94
Valor Juros Mora Dia: R$ 0,09
Após vencimento cobrar Multa de R$ 5,40
"""

# Mesmo estabelecimento Jaguaré, mas fornecedores e valores diferentes.
LOL_JAGUARE_BOLETO = """
RECIBO DO PAGADOR
FICHA DE COMPENSAÇÃO
LOL SERVIÇOS DE INTERNET LTDA
09.267.506/0001-36
LCR COM. DE MOVEIS LTDA - Jaguaré
Nº do documento
208929
Vencimento
15/05/2026
Valor do documento
200,00
"""

SKYTEF_JAGUARE_NOTA = """
991480
2EPKN8RQ
Numero da Nota
Data e Hora da Emissão
15/06/2026 16:26:00
NOTA FISCAL ELETRONICA DE SERVIÇOS - NFS-e
RPS N° 991.481 Série 1, emitido em 15/06/2026
CPF/CNPJ: 04.988.631/0001-11
SKYTEF SOLUÇÕES EM CAPTURA DE TRANSAÇÕES LTDA
TOMADOR DE SERVIÇOS
LCR COMERCIO DE MOVEIS LTDA
C.P.F. / C.N.P.J. 09.081.947/0008-15
Valor liquido a ser pago: 244,94
Data de vencimento: 01/07/2026
VALOR TOTAL DOS SERVIÇOS = 244,94
"""


def _pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(36, 36, 560, 800), text, fontsize=8)
    doc.save(path)
    doc.close()


def main() -> None:
    assert _achar_numero_nota(AUDITOR_RECIBO) == "2605"
    assert _achar_numero_nota(SKYTEF_NOTA) == "991482"
    assert _achar_numero_rps(SKYTEF_NOTA) == "991483"
    assert _achar_numero_documento_pagamento(SKYTEF_BOLETO) == "991483-01"
    assert _achar_valor(SKYTEF_NOTA) == "269,94"
    assert _achar_valor_pagamento(SKYTEF_BOLETO) == "269,94"

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        samples = {
            "auditor_nota.pdf": AUDITOR_NOTA,
            "auditor_recibo.pdf": AUDITOR_RECIBO,
            "lol_nota.pdf": LOL_NOTA,
            "lol_boleto.pdf": LOL_BOLETO,
            "skytef_nota.pdf": SKYTEF_NOTA,
            "skytef_boleto.pdf": SKYTEF_BOLETO,
            "lol_jaguare_boleto.pdf": LOL_JAGUARE_BOLETO,
            "skytef_jaguare_nota.pdf": SKYTEF_JAGUARE_NOTA,
        }
        files = []
        for name, text in samples.items():
            p = base / name
            _pdf(p, text)
            files.append(p)

        grupos = agrupar_documentos(files)
        por_num = {g.numero: g for g in grupos}

        assert len(por_num["2605"].documentos) == 2
        assert len(por_num["208938"].documentos) == 2
        assert len(por_num["991482"].documentos) == 2
        # Nao pode parear por nome de loja/arquivo quando fornecedor e valor divergem.
        assert len(por_num["208929"].documentos) == 1
        assert len(por_num["991480"].documentos) == 1

    print("[OK] Auditor: numero NFS-e pareia nota + recibo")
    print("[OK] LOL: Fatura pareia Nota de Debito + boleto")
    print("[OK] SKYTEF: RPS pareia com Numero do Documento -01")
    print("[OK] fornecedores diferentes nao sao unidos mesmo na mesma filial")


if __name__ == "__main__":
    main()
