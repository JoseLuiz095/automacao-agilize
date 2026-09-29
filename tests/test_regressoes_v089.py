from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agilize_batch import AgilizeSession, resolver_tipo_destino
from batch import _tipo_sugerido
from models import NotaDados
from tipos_agilize import ordem_pesquisa


def _lol() -> NotaDados:
    return NotaDados(
        numero="213847",
        valor="200,00",
        emissao="2026-09-02",
        vencimento="2026-09-15",
        provider_cnpj="09.267.506/0001-36",
        provider_name="LOL SERVICOS DE INTERNET LTDA",
        company_cnpj="23.448.429/0001-41",
        company_id=2,
        company_name="LEAO COMERCIO DE MOVEIS LTDA",
    )


def test_nota_de_debito_e_documentos_no_automatico():
    texto = "NOTA DE DÉBITO Fatura: 213847 LOL SERVIÇOS DE INTERNET LTDA"
    sugerido = _tipo_sugerido(texto, 40, 5)
    assert sugerido == "documentos"
    assert resolver_tipo_destino("auto", sugerido, _lol()) == "documentos"


def test_lol_forca_documentos_no_auto_como_protecao_adicional():
    # Mesmo se uma futura mudanca do parser sugerir NFS-E por engano, o CNPJ da LOL
    # continua protegido no modo Automatico.
    assert resolver_tipo_destino("auto", "nfse", _lol()) == "documentos"


def test_selecao_manual_controla_o_destino():
    assert resolver_tipo_destino("documentos", "nfse", _lol()) == "documentos"
    assert resolver_tipo_destino("nfse", "documentos", _lol()) == "nfse"


def test_historico_documentos_permanece_na_area_correta():
    assert [x.key for x in ordem_pesquisa("documentos", "documentos")] == ["documentos"]
    src = inspect.getsource(AgilizeSession.preparar_lancamento)
    assert "resolver_tipo_destino" in src
    assert "_preencher_destino_documentos" in src
    assert "referencia.get(\"tipo\") != destino" in src


if __name__ == "__main__":
    test_nota_de_debito_e_documentos_no_automatico()
    test_lol_forca_documentos_no_auto_como_protecao_adicional()
    test_selecao_manual_controla_o_destino()
    test_historico_documentos_permanece_na_area_correta()
    print("[OK] v0.8.9 - destino do lancamento separado da pesquisa historica; LOL -> Doc. - Contas a pagar")
