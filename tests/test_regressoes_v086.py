from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agilize import _linha_mesma_empresa, _linha_nfs_efetuada
from models import NotaDados


def _row(numero: str, empresa: str, situacao: str) -> list[str]:
    return [
        "", numero, "719,74", "17/08/2026", empresa,
        "32.401.507/0001-43", "AS AUDITORIA SISTEMAS E REPRESENTACOES LTDA",
        "10/09/2026", situacao, "Alecsandro Gramelick", "", "Editar",
    ]


def test_somente_efetuada_pode_ser_nota_base():
    assert _linha_nfs_efetuada(_row("2601", "LCR COMERCIO DE MOVEIS LTDA (0017-06)", "Efetuada"))
    assert not _linha_nfs_efetuada(_row("2601", "LCR COMERCIO DE MOVEIS LTDA (0017-06)", "Não possui"))
    assert not _linha_nfs_efetuada(_row("2601", "LCR COMERCIO DE MOVEIS LTDA (0017-06)", "Aguardando Entrada"))


def test_filial_lcr_precisa_ser_a_mesma():
    dados = NotaDados(
        company_cnpj="09.081.947/0017-06",
        company_id=21,
        company_name="LCR COMERCIO DE MOVEIS LTDA (0017-06)",
    )
    assert _linha_mesma_empresa(_row("2601", "LCR COMERCIO DE MOVEIS LTDA (0017-06)", "Efetuada"), dados)
    assert not _linha_mesma_empresa(_row("2583", "LCR COMERCIO DE MOVEIS LTDA (0011-10)", "Efetuada"), dados)


def test_empresa_sem_filial_continua_compativel():
    dados = NotaDados(
        company_cnpj="68.451.419/0001-01",
        company_id=41,
        company_name="MM MONTAGEM E SERVICO LTDA",
    )
    assert _linha_mesma_empresa(_row("2695", "MM MONTAGEM E SERVIÇO LTDA", "Efetuada"), dados)


if __name__ == "__main__":
    test_somente_efetuada_pode_ser_nota_base()
    test_filial_lcr_precisa_ser_a_mesma()
    test_empresa_sem_filial_continua_compativel()
    print("[OK] v0.8.6 - historico usa somente Situacao de Entrada Efetuada e mesma empresa/filial")
