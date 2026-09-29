from __future__ import annotations

import hashlib
import html
import imaplib
import re
import socket
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.policy import default
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import unquote, urlparse

Logger = Callable[[str], None]


@dataclass
class ZimbraSearchConfig:
    email: str
    senha: str
    remetente: str
    data_inicio: date
    data_fim: date
    destino: Path
    servidor: str = ""
    porta: int = 993
    pasta: str = "INBOX"


@dataclass
class MailDownloadItem:
    uid: str
    data: str
    assunto: str
    remetente: str
    pdfs: list[Path] = field(default_factory=list)
    links_manuais: list[str] = field(default_factory=list)
    chaves_nfse: list[str] = field(default_factory=list)


@dataclass
class MailDownloadResult:
    itens: list[MailDownloadItem] = field(default_factory=list)
    pdfs: list[Path] = field(default_factory=list)
    links_manuais: list[str] = field(default_factory=list)
    mensagens_lidas: int = 0


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(html.unescape(value.strip()))


def _log(logger: Optional[Logger], msg: str) -> None:
    if logger:
        logger(msg)


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for raw, charset in decode_header(value):
        if isinstance(raw, bytes):
            for enc in (charset, "utf-8", "latin-1"):
                if not enc:
                    continue
                try:
                    parts.append(raw.decode(enc, errors="replace"))
                    break
                except Exception:
                    continue
            else:
                parts.append(raw.decode("utf-8", errors="replace"))
        else:
            parts.append(str(raw))
    return "".join(parts).strip()


def _safe_filename(name: str, fallback: str = "anexo.pdf") -> str:
    name = unquote((name or "").strip()).replace("\\", "_").replace("/", "_")
    name = re.sub(r"[<>:\"|?*\x00-\x1F]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = fallback
    if len(name) > 180:
        stem = Path(name).stem[:150]
        suffix = Path(name).suffix[:20]
        name = stem + suffix
    return name


def _unique_path(folder: Path, filename: str, content: bytes | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(filename)
    target = folder / filename
    if not target.exists():
        return target
    if content is not None:
        try:
            if target.read_bytes() == content:
                return target
        except Exception:
            pass
    stem, suffix = target.stem, target.suffix
    for idx in range(2, 10000):
        candidate = folder / f"{stem} ({idx}){suffix}"
        if not candidate.exists():
            return candidate
    digest = hashlib.sha1((filename + str(datetime.now().timestamp())).encode()).hexdigest()[:8]
    return folder / f"{stem}-{digest}{suffix}"


def _extract_text_and_links(msg: Message) -> tuple[str, list[str]]:
    chunks: list[str] = []
    links: list[str] = []
    for part in msg.walk():
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get_content_disposition() or "").lower()
        if disp == "attachment":
            continue
        if ctype not in {"text/plain", "text/html"}:
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
        content = str(content or "")
        chunks.append(content)
        if ctype == "text/html":
            parser = _LinkParser()
            try:
                parser.feed(content)
                links.extend(parser.links)
            except Exception:
                pass
        links.extend(re.findall(r"https?://[^\s<>\"']+", content, flags=re.I))
    text = "\n".join(chunks)
    cleaned: list[str] = []
    seen = set()
    for link in links:
        link = html.unescape(link).strip().rstrip(".,);]>")
        if link and link not in seen:
            seen.add(link)
            cleaned.append(link)
    return text, cleaned


def _is_nfse_manual_link(url: str) -> bool:
    value = (url or "").lower()
    if not value.startswith(("http://", "https://")):
        return False
    host = (urlparse(value).hostname or "").lower()
    tokens = ("nfse", "nfs-e", "nota", "dps", "servico", "serviço")
    if "nfse" in host or "notafiscal" in host:
        return True
    return any(token in value for token in tokens) and any(x in value for x in ("consulta", "public", "chave", "access", "portal"))


def _extract_nfse_keys(text: str) -> list[str]:
    # A chave nacional da NFS-e encontrada nas amostras possui 50 digitos.
    values = re.findall(r"(?<!\d)(\d{50})(?!\d)", re.sub(r"[ .-]", "", text or ""))
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _imap_date(value: date) -> str:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{value.day:02d}-{months[value.month - 1]}-{value.year:04d}"


def _test_imap_host(host: str, port: int = 993, timeout: float = 2.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            context = ssl.create_default_context()
            with context.wrap_socket(sock, server_hostname=host):
                return True
    except Exception:
        return False


def descobrir_servidor_imap(email: str, servidor_preferido: str = "", porta: int = 993) -> str:
    preferred = (servidor_preferido or "").strip()
    if preferred:
        return preferred
    domain = (email or "").split("@")[-1].strip().lower()
    if not domain or "." not in domain:
        raise ValueError("Informe o servidor IMAP do Zimbra.")
    candidates = [f"imap.{domain}", f"mail.{domain}", f"zimbra.{domain}", f"webmail.{domain}", domain]
    for host in candidates:
        if _test_imap_host(host, porta=porta):
            return host
    raise ConnectionError(
        "Nao foi possivel descobrir automaticamente o servidor IMAP. "
        "Informe o host do Zimbra/IMAP nas configuracoes de e-mail."
    )


def testar_conexao(config: ZimbraSearchConfig) -> str:
    host = descobrir_servidor_imap(config.email, config.servidor, config.porta)
    mail = imaplib.IMAP4_SSL(host, config.porta, timeout=12)
    try:
        mail.login(config.email, config.senha)
        status, _ = mail.select(config.pasta or "INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError(f"Nao foi possivel abrir a pasta {config.pasta or 'INBOX'}.")
        return host
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def _save_pdf_attachments(msg: Message, destino: Path, uid: str, logger: Optional[Logger]) -> list[Path]:
    saved: list[Path] = []
    for idx, part in enumerate(msg.walk(), start=1):
        filename = _decode_header(part.get_filename())
        ctype = (part.get_content_type() or "").lower()
        if not filename and ctype != "application/pdf":
            continue
        if filename and not filename.lower().endswith(".pdf") and ctype != "application/pdf":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if not filename:
            filename = f"email_{uid}_anexo_{idx}.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        target = _unique_path(destino, filename, payload)
        if not target.exists():
            target.write_bytes(payload)
            _log(logger, f"PDF baixado: {target.name}")
        else:
            _log(logger, f"PDF ja existente: {target.name}")
        if target not in saved:
            saved.append(target)
    return saved


def buscar_e_baixar(config: ZimbraSearchConfig, logger: Optional[Logger] = None) -> MailDownloadResult:
    if not config.email.strip():
        raise ValueError("Informe o e-mail do Zimbra.")
    if not config.senha:
        raise ValueError("Informe a senha do Zimbra.")
    if not config.remetente.strip():
        raise ValueError("Informe o remetente a pesquisar.")
    if config.data_fim < config.data_inicio:
        raise ValueError("A data final nao pode ser anterior a data inicial.")

    destino = Path(config.destino).expanduser().resolve()
    destino.mkdir(parents=True, exist_ok=True)
    host = descobrir_servidor_imap(config.email, config.servidor, config.porta)
    _log(logger, f"Conectando ao Zimbra por IMAP: {host}:{config.porta}...")

    result = MailDownloadResult()
    mail = imaplib.IMAP4_SSL(host, config.porta, timeout=20)
    try:
        mail.login(config.email, config.senha)
        status, _ = mail.select(config.pasta or "INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError(f"Nao foi possivel abrir a pasta {config.pasta or 'INBOX'}.")

        before = config.data_fim + timedelta(days=1)
        criteria = [
            "FROM", f'"{config.remetente.strip()}"',
            "SINCE", _imap_date(config.data_inicio),
            "BEFORE", _imap_date(before),
        ]
        status, data = mail.uid("SEARCH", None, *criteria)
        if status != "OK":
            raise RuntimeError("O Zimbra nao conseguiu executar a pesquisa IMAP.")
        uids = [x.decode("ascii", errors="ignore") for x in (data[0].split() if data and data[0] else [])]
        _log(logger, f"{len(uids)} mensagem(ns) encontrada(s) no periodo.")

        for uid in reversed(uids):
            status, payload = mail.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not payload:
                continue
            raw = b""
            for item in payload:
                if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], (bytes, bytearray)):
                    raw += bytes(item[1])
            if not raw:
                continue
            msg = message_from_bytes(raw, policy=default)
            assunto = _decode_header(msg.get("Subject"))
            remetente = _decode_header(msg.get("From"))
            data_header = _decode_header(msg.get("Date"))
            item = MailDownloadItem(uid=uid, data=data_header, assunto=assunto, remetente=remetente)
            item.pdfs = _save_pdf_attachments(msg, destino, uid, logger)
            text, links = _extract_text_and_links(msg)
            item.chaves_nfse = _extract_nfse_keys(text)
            item.links_manuais = [u for u in links if _is_nfse_manual_link(u)]
            result.itens.append(item)
            result.pdfs.extend(p for p in item.pdfs if p not in result.pdfs)
            for url in item.links_manuais:
                if url not in result.links_manuais:
                    result.links_manuais.append(url)

        result.mensagens_lidas = len(result.itens)
        _log(
            logger,
            f"Concluido: {result.mensagens_lidas} mensagem(ns), {len(result.pdfs)} PDF(s), "
            f"{len(result.links_manuais)} link(s) para conferencia/download manual.",
        )
        return result
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def parse_data_br(value: str) -> date:
    value = (value or "").strip()
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except Exception:
        raise ValueError(f"Data invalida: {value}. Use dd/mm/aaaa.")


def format_data_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")
