from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from agilize import (
    _aguardar_livewire,
    _fechar_modal_sem_salvar,
    _mes_anterior,
    _preencher_create,
    _tentar_login,
)
from browsers import resolver_navegador
from config import AGILIZE_URL, PROFILE_BASE_DIR, PROFILE_DIR
from models import NotaDados
from observacao import atualizar_observacao_com_pdf, montar_observacao
from tipos_agilize import TIPOS, ordem_pesquisa

Logger = Callable[[str], None]


def _log(logger: Optional[Logger], msg: str):
    if logger:
        logger(msg)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _primeira_data(texto: str) -> tuple[datetime, str]:
    for raw in re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto or ""):
        try:
            return datetime.strptime(raw, "%d/%m/%Y"), raw
        except Exception:
            continue
    return datetime.min, ""


def _select_if_exists(page, selector: str, value: str = "", label_contains: str = "") -> bool:
    try:
        loc = page.locator(selector)
        if not loc.count() or not loc.first.is_visible():
            return False
        if value:
            loc.first.select_option(value)
            return True
        if label_contains:
            options = loc.first.locator("option")
            target = label_contains.lower()
            for i in range(options.count()):
                opt = options.nth(i)
                text = opt.inner_text().strip()
                if target in text.lower():
                    val = opt.get_attribute("value")
                    loc.first.select_option(val)
                    return True
    except Exception:
        pass
    return False


def _fill_if_exists(page, selectors: list[str], value: str) -> bool:
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() and loc.first.is_visible():
                loc.first.fill(value)
                return True
        except Exception:
            continue
    return False


def _abrir_edicao_e_ler(page, row, logger: Optional[Logger]) -> tuple[str, str]:
    edit = None
    for role, name in (("link", "Editar"), ("button", "Editar")):
        try:
            candidate = row.get_by_role(role, name=name)
            if candidate.count() and candidate.first.is_visible():
                edit = candidate.first
                break
        except Exception:
            pass
    if edit is None:
        return "", ""

    try:
        edit.click()
        page.wait_for_timeout(250)
    except Exception:
        return "", ""

    obs = ""
    aprovador = ""
    for selector in (
        "#observacao",
        "textarea[id*='observ']",
        "textarea[wire\\:model*='description']",
        "textarea[wire\\:model*='observ']",
    ):
        try:
            loc = page.locator(selector)
            if loc.count() and loc.first.is_visible():
                obs = loc.first.input_value()
                break
        except Exception:
            continue

    for selector in (
        "#user_for_approval option:checked",
        "select[id*='approval'] option:checked",
        "select[wire\\:model*='approval'] option:checked",
        "select[wire\\:model*='aprov'] option:checked",
    ):
        try:
            loc = page.locator(selector)
            if loc.count():
                aprovador = loc.first.inner_text().strip()
                if aprovador.lower().startswith(("escolha", "selecione")):
                    aprovador = ""
                break
        except Exception:
            continue

    _fechar_modal_sem_salvar(page)
    return obs, aprovador


def _buscar_em_tipo(page, dados: NotaDados, tipo_key: str, logger: Optional[Logger]):
    tipo = TIPOS[tipo_key]
    inicio, fim = _mes_anterior(dados.emissao)
    _log(logger, f"Pesquisando CNPJ em {tipo.label}...")

    page.goto(tipo.url, wait_until="domcontentloaded")
    try:
        page.locator("#searchInput").wait_for(state="visible", timeout=9000)
    except PlaywrightTimeoutError:
        _log(logger, f"{tipo.label}: tela de pesquisa diferente do mapeamento atual.")
        return None

    # Filtros são opcionais nas telas diferentes. Usa tudo o que estiver disponível.
    _fill_if_exists(
        page,
        [
            'input[wire\\:model\\.debounce\\.1000ms="filter.dateStart"]',
            'input[wire\\:model*="dateStart"]',
        ],
        inicio,
    )
    _fill_if_exists(
        page,
        [
            'input[wire\\:model\\.debounce\\.1000ms="filter.dateEnd"]',
            'input[wire\\:model*="dateEnd"]',
        ],
        fim,
    )

    if dados.company_id:
        # /nfs usa #underline_select; outras telas podem usar IDs diferentes.
        if not _select_if_exists(page, "#underline_select", value=str(dados.company_id)):
            for selector in ("select[wire\\:model*='company']", "select[id*='empresa']", "select[id*='company']"):
                if _select_if_exists(page, selector, value=str(dados.company_id)):
                    break

    # Prioriza pesquisa por documento/CNPJ do fornecedor.
    if not _select_if_exists(page, "#searchType", label_contains="Documento fornecedor"):
        if not _select_if_exists(page, "#searchType", label_contains="CNPJ"):
            _select_if_exists(page, "#searchType", label_contains="Documento")

    page.locator("#searchInput").fill(dados.provider_cnpj)
    _aguardar_livewire(page, minimo_ms=1150, timeout=5500)

    rows = page.locator("tbody tr")
    candidatos: list[tuple[datetime, int, str, str]] = []
    provider_digits = _digits(dados.provider_cnpj)
    company_digits = _digits(dados.company_cnpj)
    company_name = (dados.company_name or "").lower()

    for i in range(rows.count()):
        row = rows.nth(i)
        try:
            text = row.inner_text().strip()
        except Exception:
            continue
        if provider_digits and provider_digits not in _digits(text):
            continue
        # Se a tela não conseguiu aplicar o filtro da empresa, valida pelo texto quando possível.
        if company_digits and company_digits in _digits(text):
            company_ok = True
        elif company_name and company_name.split("(")[0].strip().lower() in text.lower():
            company_ok = True
        else:
            # Em /nfs a coluna mostra a empresa, mas não o CNPJ; o select já filtrou.
            company_ok = True
        if not company_ok:
            continue
        dt, dt_text = _primeira_data(text)
        numero = ""
        cells = row.locator("th, td")
        try:
            values = [c.strip() for c in cells.all_inner_texts()]
            if len(values) > 1:
                numero = values[1]
        except Exception:
            pass
        candidatos.append((dt, i, numero, dt_text))

    if not candidatos:
        _log(logger, f"{tipo.label}: nenhum registro para o CNPJ no mês anterior.")
        return None

    candidatos.sort(reverse=True, key=lambda item: item[0])
    _dt, row_index, numero, emissao_txt = candidatos[0]
    row = page.locator("tbody tr").nth(row_index)
    obs, aprovador = _abrir_edicao_e_ler(page, row, logger)
    _log(logger, f"Referência encontrada em {tipo.label}: {numero or 'registro'} {emissao_txt}".strip())
    return {
        "tipo": tipo.key,
        "tipo_label": tipo.label,
        "numero": numero,
        "emissao": emissao_txt,
        "observacao": obs,
        "aprovador": aprovador,
    }


def buscar_referencia_multitipo(page, dados: NotaDados, preferido: str, sugerido: str, logger: Optional[Logger]):
    if not dados.provider_cnpj or not dados.company_id:
        _log(logger, "Pesquisa de referência: CNPJ do fornecedor ou empresa não identificado.")
        return None

    ordem = ordem_pesquisa(preferido, sugerido)
    _log(logger, "Busca de histórico: " + " → ".join(t.label for t in ordem))
    primeiro_registro = None
    for tipo in ordem:
        found = _buscar_em_tipo(page, dados, tipo.key, logger)
        if not found:
            continue
        if primeiro_registro is None:
            primeiro_registro = found
        # Para reaproveitar a observacao completa/aprovador, preferimos uma referencia cujo modal
        # exponha dados reutilizáveis. Se outra área só confirmar que o CNPJ existe,
        # a pesquisa continua nas demais em vez de parar prematuramente.
        if found.get("observacao") or found.get("aprovador"):
            return found
        _log(logger, f"{found.get('tipo_label')}: CNPJ localizado, mas sem dados reutilizáveis; continuando a pesquisa.")
    if primeiro_registro:
        _log(logger, "CNPJ localizado no histórico, porém sem RATEIO/aprovador reutilizável nas telas mapeadas.")
        return primeiro_registro
    _log(logger, "Nenhum registro anterior encontrado em Notas NFS-E ou Doc. - Contas a pagar.")
    return None


class AgilizeSession:
    """Sessão persistente do navegador para preparar vários lançamentos sem bloquear o app."""

    def __init__(self, navegador: str = "auto", email: str = "", senha: str = "", logger: Optional[Logger] = None):
        self.browser = resolver_navegador(navegador)
        self.email = email
        self.senha = senha
        self.logger = logger
        self._p = None
        self.context = None
        self._logged = False

    def open(self):
        if self.context is not None:
            return
        if self.browser.key == "edge" and PROFILE_DIR.exists():
            profile_dir = PROFILE_DIR
        else:
            profile_dir = PROFILE_BASE_DIR / self.browser.key
        profile_dir.mkdir(parents=True, exist_ok=True)

        self._p = sync_playwright().start()
        _log(self.logger, f"Abrindo {self.browser.label} para a fila de lançamentos...")
        self.context = self._p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel=self.browser.channel,
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
        )

    def _ensure_login(self, page):
        page.goto(AGILIZE_URL, wait_until="domcontentloaded")
        try:
            page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=5000)
            self._logged = True
            return
        except PlaywrightTimeoutError:
            pass
        _tentar_login(page, self.email, self.senha, self.logger)
        try:
            page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=12000)
            self._logged = True
        except PlaywrightTimeoutError:
            _log(self.logger, "Aguardando login manual. A fila continuará quando a tela NFS-E estiver disponível.")
            page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=300000)
            self._logged = True

    def preparar_lancamento(
        self,
        dados: NotaDados,
        anexos_pdf: list[str],
        conferencia_pdf: str,
        tipo_preferido: str = "auto",
        tipo_sugerido: str = "nfse",
    ):
        self.open()
        assert self.context is not None
        page = self.context.new_page()
        page.set_default_timeout(15000)
        self._ensure_login(page)

        referencia = buscar_referencia_multitipo(page, dados, tipo_preferido, tipo_sugerido, self.logger)
        tipo_pagamento = dados.pagamento_tipo or "BOLETO"
        if referencia:
            obs_base = referencia.get("observacao", "")
            dados.observacao = atualizar_observacao_com_pdf(
                obs_base,
                vencimento_iso=dados.vencimento,
                tipo_pagamento=tipo_pagamento,
                banco=dados.banco,
                meio_pagamento_descricao=dados.pagamento_meio_descricao,
                referencia_periodo=dados.referencia_periodo,
                pagamento_numero_documento=dados.pagamento_numero_documento,
                nosso_numero=dados.nosso_numero,
                pagamento_valor=dados.pagamento_valor or dados.valor,
                numero_nota=dados.numero,
            )
            dados.nota_base_numero = referencia.get("numero", "")
            dados.nota_base_emissao = referencia.get("emissao", "")
            _log(
                self.logger,
                f"Observacao completa reutilizada de {referencia.get('tipo_label')} e atualizada com os dados do PDF atual.",
            )
            if referencia.get("aprovador") and not dados.aprovador:
                dados.aprovador = referencia["aprovador"]
                _log(self.logger, f"Aprovador reutilizado: {dados.aprovador}")
        elif not dados.observacao:
            dados.observacao = montar_observacao(dados.vencimento, "", tipo_pagamento)

        # O formulário de criação totalmente mapeado hoje é o NFS-E. A arquitetura
        # já pesquisa as três áreas; novos adaptadores de criação podem ser adicionados
        # sem alterar a fila ou o agrupamento de PDFs.
        page.goto(AGILIZE_URL, wait_until="domcontentloaded")
        page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=12000)
        _preencher_create(page, dados, anexos_pdf, self.logger)

        if conferencia_pdf:
            pdf_page = self.context.new_page()
            pdf_page.goto(Path(conferencia_pdf).resolve().as_uri(), wait_until="domcontentloaded")
        page.bring_to_front()
        _log(self.logger, f"Lançamento {dados.numero or '(sem referência)'} preparado. O envio continua manual.")
        return page

    def close(self):
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        self.context = None
        try:
            if self._p:
                self._p.stop()
        except Exception:
            pass
        self._p = None
