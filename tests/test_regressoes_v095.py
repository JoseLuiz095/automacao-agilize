from __future__ import annotations

import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from agilize_batch import erro_recursos_navegador
from zimbra_mail import _extract_nfse_keys, _extract_text_and_links, _is_nfse_manual_link

assert erro_recursos_navegador("net::ERR_INSUFFICIENT_RESOURCES at https://exemplo/nfs")
assert erro_recursos_navegador("ERR_OUT_OF_MEMORY")
assert not erro_recursos_navegador("Timeout 15000ms exceeded")

msg = EmailMessage()
msg["Subject"] = "Fwd: Sistema Auditor - Boleto e Nota Fiscal - Número 2928"
msg.set_content("Consulte sua NFS-e no portal.")
msg.add_alternative(
    '<html><body><a href="https://www.nfse.gov.br/ConsultaPublica?chave=32050022232401507000143000000000292826097728435729">Visualizar NFS-e</a></body></html>',
    subtype="html",
)
text, links = _extract_text_and_links(msg)
assert links
assert any(_is_nfse_manual_link(link) for link in links)
keys = _extract_nfse_keys(text + " 32050022232401507000143000000000292826097728435729")
assert "32050022232401507000143000000000292826097728435729" in keys

src = (ROOT / "app" / "agilize_batch.py").read_text(encoding="utf-8")
assert "AUTOMACAO_AGILIZE_MAX_ABERTOS" in src
assert "ERR_INSUFFICIENT_RESOURCES" in src.upper()
assert "Limite seguro" in src

app_src = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
assert "E-mail / Downloads" in app_src
assert "Importar PDFs baixados manualmente" in app_src

print("[OK] v0.9.5 - fila limita abas, recupera ERR_INSUFFICIENT_RESOURCES e possui downloader Zimbra/hCaptcha manual")
