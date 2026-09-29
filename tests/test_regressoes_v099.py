from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize import _intervalo_historico_nfse
from agilize_batch import _intervalo_historico
from models import NotaDados

# Setembro/2026 deve consultar junho, julho e agosto completos.
assert _intervalo_historico_nfse("2026-09-20") == ("2026-06-01", "2026-08-31")

dados = NotaDados()
dados.emissao = "2026-09-20"
assert _intervalo_historico("nfse", dados) == ("2026-06-01", "2026-08-31")

# Virada de ano: janeiro/2027 consulta outubro-dezembro/2026.
assert _intervalo_historico_nfse("2027-01-10") == ("2026-10-01", "2026-12-31")

batch_src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")
assert "datas confirmadas na tela" in batch_src
assert "3 meses completos anteriores" in batch_src

print("[OK] v0.9.9 - NFS-E consulta 3 meses anteriores e confirma filtros de data")
