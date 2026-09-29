from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agilize import _linha_importada_corresponde, _linha_nfs_nao_possui
from models import NotaDados


def _dados() -> NotaDados:
    return NotaDados(
        numero="2724",
        valor="719,74",
        emissao="2026-09-01",
        company_id=14,
        company_name="LCR COMERCIO DE MOVEIS LTDA (0008-15)",
        company_cnpj="09.081.947/0008-15",
        provider_cnpj="32.401.507/0001-43",
        provider_name="AS AUDITORIA SISTEMAS E REPRESENTACOES LTDA",
    )


def _linha(status="Não possui", numero="2724", valor="719,74", emissao="01/09/2026", empresa="LCR COMERCIO DE MOVEIS LTDA (0008-15)", cnpj="32.401.507/0001-43"):
    return [
        "", numero, valor, emissao, empresa, cnpj,
        "AS AUDITORIA SISTEMAS E REPRESENTACOES LTDA", "", status, "", "", "Abrir",
    ]


def test_importada_exata_e_reutilizada():
    ok, motivo = _linha_importada_corresponde(_linha(), _dados())
    assert ok, motivo
    assert _linha_nfs_nao_possui(_linha())


def test_numero_com_zeros_a_esquerda_continua_equivalente():
    ok, motivo = _linha_importada_corresponde(_linha(numero="002724"), _dados())
    assert ok, motivo


def test_nao_reutiliza_efetuada_como_destino_atual():
    ok, _ = _linha_importada_corresponde(_linha(status="Efetuada"), _dados())
    assert not ok


def test_nao_reutiliza_mesmo_numero_com_dados_divergentes():
    ok, motivo = _linha_importada_corresponde(_linha(valor="999,99"), _dados())
    assert not ok and "valor" in motivo.lower()

    ok, motivo = _linha_importada_corresponde(_linha(empresa="LCR COMERCIO DE MOVEIS LTDA (0011-10)"), _dados())
    assert not ok and "empresa" in motivo.lower()

    ok, motivo = _linha_importada_corresponde(_linha(cnpj="05.607.266/0001-10"), _dados())
    assert not ok and "cnpj" in motivo.lower()


if __name__ == "__main__":
    test_importada_exata_e_reutilizada()
    test_numero_com_zeros_a_esquerda_continua_equivalente()
    test_nao_reutiliza_efetuada_como_destino_atual()
    test_nao_reutiliza_mesmo_numero_com_dados_divergentes()
    print("[OK] v0.8.8 - reutiliza NFS-e importada em Nao possui sem duplicar lancamento")
