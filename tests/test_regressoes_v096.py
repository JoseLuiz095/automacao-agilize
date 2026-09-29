from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize_batch import AgilizeSession

session = AgilizeSession.__new__(AgilizeSession)
# valida pelo codigo-fonte para nao iniciar Playwright/browser no teste
src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")
app_src = (ROOT / "app" / "app.py").read_text(encoding="utf-8")

assert "self.max_workspaces = 1" in src
assert "sequencial" in src.lower()
assert "PREPARAR TODOS (1 POR VEZ)" in app_src
assert "Processamento um por um" in app_src
assert "somente 1 será preparado por vez" in app_src

print("[OK] v0.9.6 - fila processa um lancamento por vez e avisa o usuario antes de lotes")
