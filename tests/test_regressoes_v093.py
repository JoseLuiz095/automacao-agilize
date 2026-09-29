from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from batch import DocumentoInfo, _score_pareamento
from config import EMPRESAS
from models import NotaDados
from pdf_reader import _achar_empresa_interna, _achar_provider_cnpj
from agilize import _linha_importada_corresponde

# Nova filial LCR encontrada no Agilize / PDFs de setembro.
assert EMPRESAS["09.081.947/0029-40"] == (42, "LCR COMERCIO DE MOVEIS LTDA (0029-40)")

# Recibo combinado: CLIENTE e fornecedor aparecem no mesmo PDF. O cliente nao pode
# ser confundido com o CNPJ do fornecedor, pois isso quebrava o pareamento.
texto_recibo = """
RECIBO DA NOTA FISCAL DE SERVIÇOS ELETRÔNICA
CLIENTE:
LCR COMERCIO DE MOVEIS LTDA
CNPJ 09.081.947/0029-40
Nº NFS-e 002894
AS AUDITORIA SISTEMAS E REPRESENTAÇÕES LTDA EPP
CNPJ: 32.401.507/0001-43
VENCIMENTO 30/09/2026
"""
company_cnpj, company_id, company_name = _achar_empresa_interna(texto_recibo)
assert company_cnpj == "09.081.947/0029-40"
assert company_id == 42
assert "0029-40" in company_name
assert _achar_provider_cnpj(texto_recibo, company_cnpj) == "32.401.507/0001-43"

# Mesmo numero fiscal + empresa + fornecedor + valor devem formar um unico grupo.
a = DocumentoInfo(
    path=Path("recibo.pdf"), texto="", numero_fiscal="2894", nota_referenciada="2894",
    score_nota=8, score_pagamento=165, company_cnpj="09.081.947/0029-40",
    provider_cnpj="32.401.507/0001-43", valor="1.617,34",
)
b = DocumentoInfo(
    path=Path("danfse.pdf"), texto="", numero_fiscal="2894",
    score_nota=160, score_pagamento=0, company_cnpj="09.081.947/0029-40",
    provider_cnpj="32.401.507/0001-43", valor="1.617,34",
)
score, motivo = _score_pareamento(a, b)
assert score >= 95, (score, motivo)

# O fluxo padrao deve aceitar o registro atual pre-lancado em "Nao possui" quando
# os dados conferem, evitando criar uma segunda NFS-e.
dados = NotaDados(
    numero="2894",
    valor="1.617,34",
    emissao="2026-09-08",
    provider_cnpj="32.401.507/0001-43",
    company_cnpj="09.081.947/0029-40",
    company_id=42,
    company_name="LCR COMERCIO DE MOVEIS LTDA (0029-40)",
)
cells = [
    "", "2894", "1.617,34", "08/09/2026",
    "LCR COMERCIO DE MOVEIS LTDA (0029-40)",
    "32.401.507/0001-43", "AS AUDITORIA SISTEMAS E REPRESENTACOES LTDA",
    "30/09/2026", "Não possui", "Alecsandro Gramelick", "", "Editar",
]
ok, motivo = _linha_importada_corresponde(cells, dados)
assert ok, motivo

src = (ROOT / "app" / "agilize.py").read_text(encoding="utf-8")
assert "Verificando se a nota" in src
assert "Todos os status" in src
assert "_selecionar_empresa_por_dados" in src

print("[OK] v0.9.3 - Auditor 2894 pareado e registro existente reconhecido antes de criar nova NFS-e")
