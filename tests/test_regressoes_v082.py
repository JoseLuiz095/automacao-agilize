from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from observacao import atualizar_observacao_com_pdf  # noqa: E402
from pdf_reader import extrair_dados  # noqa: E402


def test_observacao_completa_finnet():
    base = (
        "- DADOS PARA PAGAMENTO:\n"
        "Ref. Junho/2026\n"
        "Data de Vencimento: 28/07/2026\n"
        "Meio de Pagamento: Boleto Bancário Itau (Obter no DDA)\n"
        "Número do Documento: 22300\n"
        "Nosso Número: 02230001\n"
        "Valor do Documento: R$ 700,00\n\n"
        "- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\n"
        "LOJA\n"
        "Contrato original: 01/01/2025"
    )
    atual = atualizar_observacao_com_pdf(
        base,
        vencimento_iso="2026-08-28",
        tipo_pagamento="BOLETO",
        banco="Bradesco",
        meio_pagamento_descricao="Boleto Bancário Bradesco",
        referencia_periodo="Julho/2026",
        pagamento_numero_documento="23433",
        nosso_numero="02343301",
        pagamento_valor="751,40",
        numero_nota="47736",
    )

    assert "Ref. Julho/2026" in atual
    assert "Data de Vencimento: 28/08/2026" in atual
    assert "Meio de Pagamento: Boleto Bancário Bradesco (Obter no DDA)" in atual
    assert "Número do Documento: 23433" in atual
    assert "Nosso Número: 02343301" in atual
    assert "Valor do Documento: R$ 751,40" in atual
    assert "- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\nLOJA" in atual
    # Datas livres do rateio/observacao nao devem ser trocadas.
    assert "Contrato original: 01/01/2025" in atual


def test_observacao_legada_boleto_data():
    base = (
        "- DADOS PARA PAGAMENTO:\n"
        "BOLETO 15/07/2026\n\n"
        "- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\n"
        "LOJA"
    )
    atual = atualizar_observacao_com_pdf(
        base,
        vencimento_iso="2026-08-15",
        tipo_pagamento="BOLETO",
        banco="Itau",
    )
    assert "BOLETO 15/08/2026" in atual
    assert atual.endswith("LOJA")


def test_parser_finnet_real_quando_amostra_disponivel():
    nota = Path("/mnt/data/NT_05607266000110_0000047736.pdf")
    boleto = Path("/mnt/data/BOLETO-02343301-MOVEIS_LINHARES.pdf")
    if not nota.exists() or not boleto.exists():
        return

    dados, _, _ = extrair_dados(nota, boleto)
    assert dados.numero == "47736"
    assert dados.vencimento == "2026-08-28"
    assert dados.pagamento_meio_descricao.lower().startswith("boleto banc")
    assert "Bradesco" in dados.pagamento_meio_descricao
    assert dados.referencia_periodo == "Julho/2026"
    assert dados.pagamento_numero_documento == "23433"
    assert dados.nosso_numero == "02343301"


def main() -> int:
    test_observacao_completa_finnet()
    test_observacao_legada_boleto_data()
    test_parser_finnet_real_quando_amostra_disponivel()
    print("[OK] v0.8.2 - observacao completa herdada e atualizada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
