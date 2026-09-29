from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize import (
    _linha_importada_prefixada_corresponde,
    _numero_nota_com_prefixo_indevido,
    _periodo_busca_importada_por_fornecedor,
)
from models import NotaDados


def _dados():
    return NotaDados(
        numero="2721",
        valor="1.621,00",
        emissao="2026-09-21",
        company_id=49,
        company_name="LCR COMERCIO DE MOVEIS LTDA (0011-49)",
        provider_cnpj="46.882.111/0001-70",
        provider_name="STARTING HUB DE INOVACAO LTDA",
    )


def _linha(numero="2600000002721", valor="1.621,00", emissao="21/09/2026", empresa="LCR COMERCIO DE MOVEIS LTDA (0011-49)", cnpj="46.882.111/0001-70", status="Não possui"):
    return [
        "", numero, valor, emissao, empresa, cnpj,
        "STARTING HUB DE INOVACAO LTDA", "", status, "", "", "Ver nota",
    ]


assert _numero_nota_com_prefixo_indevido("2600000002721", "2721")
assert not _numero_nota_com_prefixo_indevido("12721", "2721")
assert not _numero_nota_com_prefixo_indevido("2721", "2721")

ok, motivo = _linha_importada_prefixada_corresponde(_linha(), _dados())
assert ok, motivo

ok, motivo = _linha_importada_prefixada_corresponde(_linha(valor="1.620,00"), _dados())
assert not ok and "valor" in motivo.lower()

ok, motivo = _linha_importada_prefixada_corresponde(_linha(cnpj="00.000.000/0001-00"), _dados())
assert not ok and "cnpj" in motivo.lower()

ok, motivo = _linha_importada_prefixada_corresponde(_linha(emissao="20/09/2026"), _dados())
assert not ok and "emissao" in motivo.lower()

inicio, fim = _periodo_busca_importada_por_fornecedor("2026-09-21")
assert inicio == "2026-06-01", (inicio, fim)
assert fim == "2026-09-30", (inicio, fim)

src = (ROOT / "app" / "agilize.py").read_text(encoding="utf-8")
assert "fallback seguro de fornecedor/prefixo" in src
assert "numero cadastrado com prefixo indevido" in src

bat = (ROOT / "FERRAMENTAS" / "07_PUBLICAR_VERSAO.bat").read_text(encoding="utf-8")
assert "push origin main" in bat.lower()
assert "reset --mixed origin/main" in bat.lower()
assert "a release nao sera publicada" in bat.lower()

print("[OK] v0.9.11 - nota prefixada localizada com seguranca e publicador sincroniza o codigo-fonte")
