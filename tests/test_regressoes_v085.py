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


def test_modal_novo_livewire_extrai_observacao():
    payload = {
        "fingerprint": {
            "id": "TQmMqmYaYHBf35TvlV9G",
            "name": "modals.nfs.edit-nfs",
            "locale": "pt_BR",
            "path": "nfs",
            "method": "GET",
        },
        "serverMemo": {
            "data": {
                "nfs": {
                    "description": "- DADOS PARA PAGAMENTO:\nBOLETO 10/09/2026\n\n- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\nLOJA",
                    "user_for_approval_id": 47,
                    "number": "2601",
                    "provider_cnpj": "32.401.507/0001-43",
                    "company_id": 21,
                }
            }
        },
    }
    raw = html.escape(json.dumps(payload, ensure_ascii=False), quote=True)
    nfs = _parse_initial_livewire_edicao(raw)
    assert nfs["number"] == "2601"
    assert nfs["user_for_approval_id"] == 47
    assert "RATEIO" in nfs["description"]
    assert "LOJA" in nfs["description"]


def test_componente_errado_nao_e_usado():
    payload = {
        "fingerprint": {"name": "nfs.nfs-lista"},
        "serverMemo": {"data": {"nfs": {"description": "NAO USAR"}}},
    }
    assert _parse_initial_livewire_edicao(json.dumps(payload)) == {}


if __name__ == "__main__":
    test_modal_novo_livewire_extrai_observacao()
    test_componente_errado_nao_e_usado()
    print("[OK] v0.8.5 - modal novo openNfsModal/edit-nfs extrai observacao via Livewire")
