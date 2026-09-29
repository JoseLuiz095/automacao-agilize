from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize import _status_ja_processado

assert _status_ja_processado("Aguardando Aprovação")
assert _status_ja_processado("Aguardando Aprovacao")
assert _status_ja_processado("Efetuada")
assert not _status_ja_processado("Não possui")
assert not _status_ja_processado("Aguardando Correção")

app_src = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
assert 'self.nav_email =' not in app_src
assert '_build_email_downloads(self._scrollable_page' not in app_src

batch_src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")
assert 'Historico/anexos nao serao reprocessados' in batch_src
assert '_historico_cache' in batch_src

agilize_src = (ROOT / "app" / "agilize.py").read_text(encoding="utf-8")
assert 'anexo_obrigatorio' in agilize_src
assert 'td:last-child button' in agilize_src

print('[OK] v0.9.8 - status ja processado, fallback de acao, anexo opcional, cache e aba Downloads removida')
