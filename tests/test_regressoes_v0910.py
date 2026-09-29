from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import agilize

src = (ROOT / "app" / "agilize.py").read_text(encoding="utf-8")
batch_src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")

assert hasattr(agilize, "_aguardar_pesquisa_livewire")
assert "duas leituras" in (agilize._aguardar_pesquisa_livewire.__doc__ or "")
assert "_aguardar_pesquisa_livewire(page, minimo_ms=1800" in src
# The documents lookup now delegates its wait/date confirmation to a shared helper.
assert "_aguardar_pesquisa_livewire" in batch_src
assert "_pesquisar_lista_com_periodo" in batch_src
assert hasattr(agilize, "_pesquisar_lista_com_periodo")
assert "minimo_ms=1800 if tipo_key == \"nfse\" else 1700" in batch_src

print("[OK] v0.9.10 - pesquisas aguardam a grade do Livewire estabilizar antes da leitura")
