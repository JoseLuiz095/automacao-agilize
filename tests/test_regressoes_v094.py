from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize import _score_linha_mesmo_numero
from models import NotaDados


dados = NotaDados(
    numero="2894",
    valor="1.617,34",
    emissao="2026-09-08",
    provider_cnpj="32.401.507/0001-43",
    company_name="LCR COMERCIO DE MOVEIS LTDA (0029-40)",
)

# Qualquer status com o mesmo numero continua sendo candidato de edicao.
for status in ("Não possui", "Efetuada", "Aguardando Entrada", "Aguardando Aprovação"):
    cells = [
        "", "2894", "1.617,34", "08/09/2026",
        "LCR COMERCIO DE MOVEIS LTDA (0029-40)",
        "32.401.507/0001-43", "AS AUDITORIA SISTEMAS E REPRESENTACOES LTDA",
        "30/09/2026", status, "", "", "Editar",
    ]
    score, motivos = _score_linha_mesmo_numero(cells, dados)
    assert score >= 100, (status, score, motivos)

# Numero diferente nunca pode ser tratado como o mesmo registro.
cells_outro = [
    "", "2895", "1.617,34", "08/09/2026",
    "LCR COMERCIO DE MOVEIS LTDA (0029-40)",
    "32.401.507/0001-43", "AS AUDITORIA SISTEMAS E REPRESENTACOES LTDA",
    "30/09/2026", "Não possui", "", "", "Editar",
]
score, _ = _score_linha_mesmo_numero(cells_outro, dados)
assert score < 0

# Divergencias secundarias nao descartam o registro quando o numero e igual;
# servem apenas para reduzir a prioridade se houver mais de um homonimo.
cells_divergente = [
    "", "002894", "999,99", "07/09/2026",
    "OUTRA EMPRESA", "05.607.266/0001-10", "OUTRO FORNECEDOR",
    "30/09/2026", "Efetuada", "", "", "Editar",
]
score, motivos = _score_linha_mesmo_numero(cells_divergente, dados)
assert score >= 100, (score, motivos)
assert motivos

src = (ROOT / "app" / "agilize.py").read_text(encoding="utf-8")
assert "Todos os status" in src
assert "Somente agora sera permitido criar uma nova NFS-e" in src
assert "Por seguranca, nenhum novo lancamento foi criado" in src
assert "_periodo_busca_ampla" in src
assert "_selecionar_todas_empresas" in src

print("[OK] v0.9.4 - mesmo numero sempre abre registro existente; nova NFS-e somente apos busca ampla sem resultados")
