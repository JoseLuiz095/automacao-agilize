from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def ok(name: str):
    print(f"[OK] {name}")


def main() -> int:
    version = (ROOT / "VERSAO.txt").read_text(encoding="utf-8-sig").strip()
    if not version:
        raise RuntimeError("VERSAO.txt vazio")
    ok(f"VERSAO.txt = {version}")

    for rel in [
        "assets/automacao-agilize.ico",
        "assets/automacao-agilize.png",
        "installer/AutomacaoAgilize.iss",
        "build/AutomacaoAgilize.spec",
    ]:
        if not (ROOT / rel).exists():
            raise RuntimeError(f"Arquivo obrigatorio ausente: {rel}")
    ok("estrutura obrigatoria")

    import models  # noqa: F401
    import config  # noqa: F401
    import browsers  # noqa: F401
    import credentials  # noqa: F401
    import pdf_reader  # noqa: F401
    import agilize  # noqa: F401
    import agilize_batch  # noqa: F401
    import batch  # noqa: F401
    import tipos_agilize  # noqa: F401
    import updater  # noqa: F401
    import resources  # noqa: F401
    from observacao import extrair_rateio, montar_observacao
    from version import __version__

    if __version__ != version:
        raise RuntimeError(f"Versao do app ({__version__}) difere de VERSAO.txt ({version})")
    ok("imports completos")

    base = (
        "- DADOS PARA PAGAMENTO:\nBOLETO 15/07/2026\n\n"
        "- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\nLOJA"
    )
    if extrair_rateio(base) != "LOJA":
        raise RuntimeError("Falha ao extrair RATEIO")
    atual = montar_observacao("2026-08-15", "LOJA", "BOLETO")
    if "BOLETO 15/08/2026" not in atual or not atual.endswith("LOJA"):
        raise RuntimeError("Falha ao montar observacao")
    ok("regra de observacao/rateio")

    print("RESULTADO: projeto valido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
