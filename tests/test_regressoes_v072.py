from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))


def test_search_order_without_nfe() -> None:
    from tipos_agilize import ordem_pesquisa
    assert [t.key for t in ordem_pesquisa("auto", "nfse")] == ["nfse", "documentos"]
    assert [t.key for t in ordem_pesquisa("auto", "documentos")] == ["documentos", "nfse"]
    assert "nfe" not in [t.key for t in ordem_pesquisa("nfe", "nfe")]


def test_cte_false_positive_removed() -> None:
    from batch import _tipo_sugerido
    texto = "Comprovante de entrega com as caracteristicas do boleto. FICHA DE COMPENSACAO"
    assert _tipo_sugerido(texto, 0, 50) == "documentos"


def test_real_internet_examples_when_available() -> None:
    from batch import agrupar_documentos
    base = ROOT.parent
    docs = [
        base / "02027 - CD EUNAPOLIS BOLETO.PDF",
        base / "02027 - CD EUNAPOLIS.PDF",
        base / "12001 - WI BOLETO.PDF",
        base / "12001 - WI.PDF",
        base / "02026 - ITAMARAJU.PDF",
        base / "13001 - LEAO BOLETO.PDF",
    ]
    if not all(p.exists() for p in docs):
        return
    grupos = agrupar_documentos(docs)
    refs = {g.numero: g for g in grupos}

    assert "208942" in refs and len(refs["208942"].documentos) == 2
    assert refs["208942"].dados.company_cnpj == "09.081.947/0027-88"
    assert refs["208942"].dados.provider_cnpj == "09.267.506/0001-36"
    assert refs["208942"].dados.provider_name == "LOL SERVIÇOS DE INTERNET LTDA"
    assert refs["208942"].dados.emissao == "2026-05-11"
    assert refs["208942"].dados.vencimento == "2026-05-15"
    assert refs["208942"].tipo_sugerido == "documentos"

    assert "209041" in refs and len(refs["209041"].documentos) == 2
    assert refs["209041"].dados.company_cnpj == "23.284.146/0001-01"
    assert refs["209041"].dados.emissao == "2026-05-11"
    assert refs["209041"].dados.vencimento == "2026-05-15"

    assert "208941" in refs and len(refs["208941"].documentos) == 1
    assert refs["208941"].dados.company_cnpj == "09.081.947/0026-05"
    assert refs["208941"].dados.provider_name == "LOL SERVIÇOS DE INTERNET LTDA"
    assert refs["208941"].dados.emissao == "2026-05-11"

    assert "208945" in refs and len(refs["208945"].documentos) == 1
    assert refs["208945"].dados.company_cnpj == "23.448.429/0001-41"
    assert refs["208945"].dados.vencimento == "2026-05-15"


def main() -> int:
    test_search_order_without_nfe()
    print("[OK] pesquisa sem NF-e/CT-e")
    test_cte_false_positive_removed()
    print("[OK] falso positivo CTE removido")
    test_real_internet_examples_when_available()
    print("[OK] notas de debito / boletos de internet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
