from __future__ import annotations

import re
import time
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from browsers import resolver_navegador
from config import AGILIZE_URL, PROFILE_DIR, PROFILE_BASE_DIR
from models import NotaDados
from observacao import atualizar_observacao_com_pdf, montar_observacao

Logger = Callable[[str], None]


def _log(logger: Optional[Logger], msg: str):
    if logger:
        logger(msg)


def _mes_anterior(emissao_iso: str):
    if emissao_iso:
        base = datetime.strptime(emissao_iso, "%Y-%m-%d")
    else:
        base = datetime.now()

    if base.month == 1:
        year, month = base.year - 1, 12
    else:
        year, month = base.year, base.month - 1

    last_day = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def _esperar_lista(page, timeout=15000):
    page.locator("#searchInput").wait_for(state="visible", timeout=timeout)


def _esperar_modal(page, timeout=15000):
    page.locator("#modal-container").wait_for(state="visible", timeout=timeout)


def _aguardar_livewire(page, minimo_ms: int = 250, timeout: int = 5000):
    """Espera apenas o necessario para a atualizacao Livewire terminar.

    Substitui os sleeps fixos longos das versoes anteriores e deixa o fluxo mais rapido.
    """
    page.wait_for_timeout(minimo_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass


def _fechar_modal_sem_salvar(page):
    try:
        cancel = page.locator("#modal-container").get_by_role("button", name="Cancelar")
        if cancel.count() and cancel.first.is_visible():
            cancel.first.click()
            page.locator("#modal-container").wait_for(state="hidden", timeout=10000)
            return
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
        page.locator("#modal-container").wait_for(state="hidden", timeout=10000)
    except Exception:
        pass


def _primeiro_visivel(page, selectors: list[str]):
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() and loc.first.is_visible():
                return loc.first
        except Exception:
            continue
    return None


def _tentar_login(page, email: str, senha: str, logger: Optional[Logger]) -> bool:
    if not email or not senha:
        return False

    _log(logger, "Sessao expirada. Tentando login automatico...")

    email_input = _primeiro_visivel(
        page,
        [
            'input[type="email"]',
            'input[name="email"]',
            '#email',
            'input[autocomplete="email"]',
            'input[name="username"]',
        ],
    )
    senha_input = _primeiro_visivel(
        page,
        [
            'input[type="password"]',
            'input[name="password"]',
            '#password',
            'input[autocomplete="current-password"]',
        ],
    )

    if email_input is None or senha_input is None:
        _log(logger, "Tela de login diferente do esperado. Login manual liberado.")
        return False

    email_input.fill(email)
    senha_input.fill(senha)

    for nome in ("Entrar", "Login", "Acessar", "Sign in"):
        try:
            botao = page.get_by_role("button", name=nome)
            if botao.count() and botao.first.is_visible():
                botao.first.click()
                _log(logger, "Credenciais enviadas ao Agilize.")
                return True
        except Exception:
            pass

    try:
        submit = page.locator('button[type="submit"], input[type="submit"]')
        if submit.count() and submit.first.is_visible():
            submit.first.click()
            _log(logger, "Credenciais enviadas ao Agilize.")
            return True
    except Exception:
        pass

    return False


def _buscar_nota_base(page, dados: NotaDados, logger: Optional[Logger]) -> tuple[str, str, str]:
    """Retorna observacao, aprovador e descricao da nota-base do mes anterior."""
    if not dados.provider_cnpj or not dados.company_id:
        _log(logger, "Nota-base: CNPJ do fornecedor ou empresa nao identificado.")
        return "", "", ""

    inicio, fim = _mes_anterior(dados.emissao)
    _log(logger, "Buscando observacao completa e aprovador na nota do mes anterior...")

    _esperar_lista(page)

    # Ajusta os filtros primeiro e deixa o campo de busca por ultimo. Os inputs de data
    # usam debounce de 1000 ms no Livewire; uma unica espera curta cobre o conjunto.
    page.locator('input[wire\\:model\\.debounce\\.1000ms="filter.dateStart"]').fill(inicio)
    page.locator('input[wire\\:model\\.debounce\\.1000ms="filter.dateEnd"]').fill(fim)
    page.locator("#underline_select").select_option(str(dados.company_id))
    page.locator("#searchType").select_option(label="Documento fornecedor")
    page.locator("#searchInput").fill(dados.provider_cnpj)
    _aguardar_livewire(page, minimo_ms=1150, timeout=5000)

    rows = page.locator("tbody tr")
    candidatos = []
    for i in range(rows.count()):
        row = rows.nth(i)
        try:
            cells = [x.strip() for x in row.locator("th, td").all_inner_texts()]
        except Exception:
            continue
        if len(cells) < 12:
            continue
        cnpj = cells[5]
        emissao_txt = cells[3]
        empresa_txt = cells[4]
        if re.sub(r"\D", "", dados.provider_cnpj) not in re.sub(r"\D", "", cnpj):
            continue
        try:
            emissao_dt = datetime.strptime(emissao_txt, "%d/%m/%Y")
        except Exception:
            emissao_dt = datetime.min
        candidatos.append((emissao_dt, i, cells[1], emissao_txt, empresa_txt))

    if not candidatos:
        _log(logger, "Nenhuma nota-base encontrada para esta empresa e fornecedor no mes anterior.")
        return "", "", ""

    candidatos.sort(reverse=True, key=lambda x: x[0])
    _, row_index, numero, emissao_txt, empresa_txt = candidatos[0]
    _log(logger, f"Nota-base encontrada: {numero} - {emissao_txt} - {empresa_txt}")

    rows = page.locator("tbody tr")
    row = rows.nth(row_index)
    row.get_by_role("link", name="Editar").click()
    _esperar_modal(page)

    obs = ""
    aprovador = ""
    try:
        obs = page.locator("#observacao").input_value()
    except Exception:
        pass
    try:
        aprovador = page.locator("#user_for_approval option:checked").inner_text().strip()
        if aprovador.lower().startswith("escolha"):
            aprovador = ""
    except Exception:
        pass

    if obs.strip():
        _log(logger, "Observacao completa recuperada da nota-base.")
    else:
        _log(logger, "Nota-base encontrada, mas a observacao esta vazia.")

    _fechar_modal_sem_salvar(page)
    return obs, aprovador, f"{numero} - {emissao_txt}"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _esperar_debounce_fornecedor(page, timeout: int = 5000):
    """O campo usa wire:model.debounce.800ms; nao podemos disparar outro rerender antes disso."""
    page.wait_for_timeout(900)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass


def _preencher_cnpj(page, cnpj: str, provider_name: str, logger: Optional[Logger]):
    """Preenche o CNPJ como um usuario e aguarda o Livewire buscar o nome do fornecedor.

    Nas versoes anteriores o fluxo seguia antes dos 800 ms de debounce. Quando outro
    campo provocava um rerender, o servidor ainda tinha provider_cnpj vazio e apagava
    o valor da tela. Aqui o CNPJ e resolvido completamente antes dos demais campos.
    """
    campo = page.locator("#fornecedor")
    campo.wait_for(state="visible", timeout=10000)
    campo.click()
    campo.press("Control+A")
    campo.press_sequentially(cnpj, delay=20)
    _esperar_debounce_fornecedor(page)

    def valor_atual():
        try:
            return page.locator("#fornecedor").input_value()
        except Exception:
            return ""

    # Se o Livewire substituiu o elemento antes de persistir o valor, repete uma vez
    # usando um evento input explicito e espera novamente o debounce de 800 ms.
    if _digits(valor_atual()) != _digits(cnpj):
        campo = page.locator("#fornecedor")
        campo.evaluate(
            """(el, value) => {
                el.focus();
                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }""",
            cnpj,
        )
        _esperar_debounce_fornecedor(page)

    final = valor_atual()
    if _digits(final) != _digits(cnpj):
        raise RuntimeError(
            f"O Agilize nao manteve o CNPJ do fornecedor {cnpj} no formulario. "
            "O preenchimento foi interrompido para evitar um lancamento sem fornecedor."
        )

    _log(logger, f"CNPJ do fornecedor confirmado no formulario: {cnpj}")

    # O proprio Agilize deve preencher o nome a partir do CNPJ. Aguarda alguns
    # instantes pelo retorno. So usa o nome lido do PDF como fallback.
    try:
        page.wait_for_function(
            "() => (document.querySelector('#nome_fornecedor')?.value || '').trim().length > 0",
            timeout=4500,
        )
    except PlaywrightTimeoutError:
        pass

    nome = page.locator("#nome_fornecedor")
    try:
        nome_atual = nome.input_value().strip()
    except Exception:
        nome_atual = ""

    if nome_atual:
        _log(logger, f"Nome do fornecedor retornado pelo Agilize: {nome_atual}")
    elif provider_name:
        nome.fill(provider_name)
        _log(logger, "Nome do fornecedor nao retornou pelo CNPJ; usado nome do PDF como contingencia.")


def _preencher_create(page, dados: NotaDados, anexos_pdf: list[str], logger: Optional[Logger]):
    _log(logger, "Abrindo formulario Enviar Nota...")
    page.get_by_role("button", name="Enviar Nota").click()
    _esperar_modal(page)

    # Primeiro executamos apenas os campos que provocam rerender no Livewire.
    # Depois disso os demais inputs podem ser preenchidos rapidamente, sem sleeps.
    if dados.company_id:
        page.locator("#empresa").select_option(str(dados.company_id))
        _aguardar_livewire(page, minimo_ms=220, timeout=4000)

    if dados.provider_cnpj:
        _preencher_cnpj(page, dados.provider_cnpj, dados.provider_name, logger)

    if dados.numero:
        page.locator("#numero").fill(str(dados.numero))
    if dados.valor:
        page.locator("#valor").fill(dados.valor)
    if dados.emissao:
        page.locator("#issued").fill(dados.emissao)

    if dados.aprovador:
        try:
            select = page.locator("#user_for_approval")
            option = select.locator("option", has_text=dados.aprovador)
            if option.count() == 0:
                _aguardar_livewire(page, minimo_ms=200, timeout=3500)
            select.select_option(label=dados.aprovador)
        except Exception:
            _log(logger, f"Aprovador '{dados.aprovador}' nao estava disponivel para esta empresa.")

    if dados.observacao:
        page.locator("#observacao").fill(dados.observacao)

    if dados.vencimento:
        page.locator('#due_date\\.0').fill(dados.vencimento)

    anexos = [str(Path(p).resolve()) for p in anexos_pdf if p]
    if not anexos:
        raise RuntimeError("Nenhum PDF foi informado para o campo Anexo do Agilize.")
    page.locator("#file_input").set_input_files(anexos)
    _log(logger, f"{len(anexos)} PDF(s) adicionados ao campo Anexo do Agilize.")

    _log(logger, "Formulario preenchido. O envio final continua manual.")


def abrir_e_preencher(
    dados: NotaDados,
    anexos_pdf: list[str],
    conferencia_pdf: str,
    navegador: str = "auto",
    logger: Optional[Logger] = None,
    email: str = "",
    senha: str = "",
):
    browser = resolver_navegador(navegador)

    # Mantem o perfil Edge das versoes anteriores para preservar a sessao ja autenticada.
    if browser.key == "edge" and PROFILE_DIR.exists():
        profile_dir = PROFILE_DIR
    else:
        profile_dir = PROFILE_BASE_DIR / browser.key
    profile_dir.mkdir(parents=True, exist_ok=True)

    p = sync_playwright().start()
    context = None
    try:
        _log(logger, f"Abrindo {browser.label}...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel=browser.channel,
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(15000)

        page.goto(AGILIZE_URL, wait_until="domcontentloaded")

        try:
            page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=6000)
        except PlaywrightTimeoutError:
            _tentar_login(page, email, senha, logger)
            try:
                page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=12000)
            except PlaywrightTimeoutError:
                _log(logger, "Aguardando login manual. A automacao continua ao abrir a tela NFS-E.")
                page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=300000)

        obs_base, aprovador_base, nota_base = _buscar_nota_base(page, dados, logger)
        tipo_pagamento = dados.pagamento_tipo or "BOLETO"
        if obs_base:
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
            dados.nota_base_numero = nota_base.split(" - ")[0] if nota_base else ""
            dados.nota_base_emissao = nota_base.split(" - ")[1] if " - " in nota_base else ""
            _log(logger, "Observacao completa do mes anterior reutilizada e atualizada com os dados do PDF atual.")
        elif not dados.observacao:
            dados.observacao = montar_observacao(dados.vencimento, "", tipo_pagamento)
            _log(logger, "Sem nota-base: rateio ficou vazio para conferencia manual.")

        if aprovador_base and not dados.aprovador:
            dados.aprovador = aprovador_base
            _log(logger, f"Aprovador reutilizado: {aprovador_base}")

        _preencher_create(page, dados, anexos_pdf, logger)

        pdf_page = context.new_page()
        pdf_page.goto(Path(conferencia_pdf).resolve().as_uri(), wait_until="domcontentloaded")
        page.bring_to_front()
        _log(logger, "Documento de referencia aberto em uma segunda aba para conferencia.")
        _log(logger, "Revise os dados e clique em Enviar manualmente.")

        while True:
            try:
                if not context.pages:
                    break
                time.sleep(1)
            except Exception:
                break
    finally:
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass
