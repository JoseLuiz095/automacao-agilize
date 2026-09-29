from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agilize import _parse_initial_livewire_edicao


def test_payload_realista_com_barras_e_quebras():
    payload = {
        "fingerprint": {"name": "modals.nfs.edit-nfs"},
        "serverMemo": {
            "data": {
                "nfs": {
                    "description": "- DADOS PARA PAGAMENTO:\nBOLETO 10/09/2026\n\n- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\nLOJA",
                    "user_for_approval_id": 47,
                    "provider_cnpj": "32.401.507/0001-43",
                    "number": "2601",
                }
            }
        },
    }
    raw = html.escape(json.dumps(payload, ensure_ascii=False).replace("/", "\\/"), quote=True)
    nfs = _parse_initial_livewire_edicao(raw)
    assert nfs["number"] == "2601"
    assert nfs["user_for_approval_id"] == 47
    assert "BOLETO 10/09/2026" in nfs["description"]
    assert "LOJA" in nfs["description"]


def test_payload_de_outro_componente_nao_e_aceito():
    payload = {
        "fingerprint": {"name": "modals.nfs.create-nfs"},
        "serverMemo": {"data": {"nfs": {"description": "NAO COPIAR"}}},
    }
    assert _parse_initial_livewire_edicao(json.dumps(payload)) == {}


if __name__ == "__main__":
    test_payload_realista_com_barras_e_quebras()
    test_payload_de_outro_componente_nao_e_aceito()
    print("[OK] v0.8.7 - payload da observacao e isolamento do modal de edicao")
