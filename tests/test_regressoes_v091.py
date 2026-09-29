from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from tipos_agilize import ordem_pesquisa
from agilize_batch import resolver_tipo_destino, erro_navegador_fechado
from models import NotaDados

# Doc. - Contas a pagar e estrito: nao deve cair em NFS-E/CNPJ para buscar historico.
assert [x.key for x in ordem_pesquisa("documentos", "documentos")] == ["documentos"]
assert [x.key for x in ordem_pesquisa("auto", "documentos")] == ["documentos"]

# LOL sempre vai para documentos no Automatico.
d = NotaDados(provider_cnpj="09.267.506/0001-36", provider_name="LOL SERVIÇOS DE INTERNET LTDA")
assert resolver_tipo_destino("auto", "nfse", d) == "documentos"

# Erro reportado pelo usuario precisa disparar recuperacao automatica do navegador.
assert erro_navegador_fechado(RuntimeError("Target page, context or browser has been closed"))

src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")
assert "valor_busca = fornecedor_busca" in src
assert "campo Buscar confirmado com o nome" in src
assert "Destino resolvido antes da pesquisa historica" in src
assert "buscar_referencia_multitipo(page, dados, destino, destino" in src
assert "valor de busca historica" in src

app_src = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
assert "Reabrindo a sessao e tentando este lancamento novamente" in app_src
assert '"Reconectando"' in app_src

print("[OK] v0.9.1 - documentos busca por nome, destino resolvido antes do historico e navegador se recupera de TargetClosed")
