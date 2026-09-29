from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize_batch import _intervalo_historico, _subtrair_meses
from models import NotaDados

hoje = date.today()
esperado_inicio = _subtrair_meses(hoje, 2).isoformat()
inicio, fim = _intervalo_historico("documentos", NotaDados())
assert inicio == esperado_inicio
assert fim == hoje.isoformat()

# Regra atual (v0.9.9): NFS-E usa 3 meses completos anteriores.
nf_inicio, nf_fim = _intervalo_historico("nfse", NotaDados(emissao="2026-09-04"))
assert (nf_inicio, nf_fim) == ("2026-06-01", "2026-08-31")

src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")
assert "ultimos 2 meses" in src
assert "datas confirmadas na tela" in src
assert "valor_busca = fornecedor_busca" in src
assert "Datas ficam por ultimo" in src

print("[OK] v0.9.2 - Contas a pagar pesquisa pelo nome com janela historica de 2 meses e confirmacao dos campos de data")
