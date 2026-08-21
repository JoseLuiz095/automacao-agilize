from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))


def test_updater_scenarios() -> None:
    import updater

    original_release = updater._release_snapshot
    original_source = updater._source_snapshot
    try:
        updater._release_snapshot = lambda: {
            "version": "99.0.0",
            "release_url": "https://example/release",
            "notes": "",
            "download_url": "https://example/setup.exe",
            "asset_name": "AutomacaoAgilize-Setup.exe",
            "checksum_url": "https://example/setup.exe.sha256",
        }
        updater._source_snapshot = lambda: {"version": "99.0.0", "branch": "main"}
        info = updater.verificar_atualizacao()
        assert info.available is True
        assert info.can_install is True
        assert info.latest_version == "99.0.0"
    finally:
        updater._release_snapshot = original_release
        updater._source_snapshot = original_source


def test_queue_button_state() -> None:
    import tkinter as tk

    if "tkinterdnd2" not in sys.modules:
        fake_mod = types.ModuleType("tkinterdnd2")
        fake_mod.DND_FILES = "DND_FILES"
        fake_mod.TkinterDnD = types.SimpleNamespace(Tk=tk.Tk)
        sys.modules["tkinterdnd2"] = fake_mod

    import app

    class Widget:
        def __init__(self):
            self.state = None
        def configure(self, **kwargs):
            if "state" in kwargs:
                self.state = kwargs["state"]

    class Var:
        def __init__(self): self.value = ""
        def set(self, value): self.value = value

    obj = object.__new__(app.App)
    obj.grupos = []
    obj.pdfs = []
    obj.btn_processar = Widget()
    obj.btn_selected = Widget()
    obj.status_docs = Var()
    obj.queue_summary_var = Var()
    obj.anexo_status_var = Var()
    obj.status_execucao = Var()
    app.App._sync_document_state(obj)
    assert obj.btn_processar.state == "disabled"

    obj.grupos = [object()]
    obj.pdfs = [object()]
    app.App._sync_document_state(obj)
    assert obj.btn_processar.state == "normal"
    assert obj.btn_selected.state == "normal"


def test_batch_pairing_with_real_examples_when_available() -> None:
    # O teste é opcional fora do ambiente de desenvolvimento. Quando os exemplos
    # estiverem ao lado do projeto, valida a associação independente da ordem.
    candidates = [
        ROOT.parent / "002695_900_2608170935-1.PDF",
        ROOT.parent / "32050022232401507000143000000000269526086560820946.pdf",
    ]
    if not all(p.exists() for p in candidates):
        return
    from batch import agrupar_documentos
    grupos = agrupar_documentos(list(reversed(candidates)))
    assert len(grupos) == 1
    assert grupos[0].numero == "2695"
    assert len(grupos[0].documentos) == 2


def main() -> int:
    test_updater_scenarios()
    print("[OK] updater")
    test_queue_button_state()
    print("[OK] fila habilita processamento")
    test_batch_pairing_with_real_examples_when_available()
    print("[OK] agrupamento")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
