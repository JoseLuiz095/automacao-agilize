from __future__ import annotations

import re
import calendar
import gc
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from agilize import (
    _abrir_modal_edicao,
    _aguardar_livewire,
    _aguardar_pesquisa_livewire,
    _fechar_modal_sem_salvar,
    _ler_dados_modal_edicao,
    _linha_mesma_empresa,
    _linha_nfs_efetuada,
    _localizar_registro_existente,
    _status_ja_processado,
    _mes_anterior,
    _intervalo_historico_nfse,
    _preencher_campos_complementares,
    _preencher_cnpj,
    _preencher_destino,
    _primeiro_visivel,
    _selecionar_status_efetuada,
    _selecionar_empresa_por_dados,
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


def erro_navegador_fechado(exc: BaseException) -> bool:
    """Reconhece falhas transitórias quando a janela/contexto Chromium foi encerrada.

    Playwright pode devolver mensagens ligeiramente diferentes conforme a versao.
    Mantemos a deteccao textual para funcionar tanto no EXE quanto no ambiente dev.
    """
    texto = str(exc or "").lower()
    marcadores = (
        "target page, context or browser has been closed",
        "target page, context or browser has been closed",
        "browser has been closed",
        "context has been closed",
        "page has been closed",
        "target closed",
    )
    return any(m in texto for m in marcadores)




def erro_recursos_navegador(exc: BaseException) -> bool:
    """Reconhece falhas de esgotamento/transiente de recursos do Chromium."""
    texto = str(exc or "").lower()
    marcadores = (
        "err_insufficient_resources",
        "net::err_insufficient_resources",
        "insufficient resources",
        "err_out_of_memory",
        "out of memory",
    )
    return any(m in texto for m in marcadores)


def _navegar_resiliente(page, url: str, logger: Optional[Logger] = None, cleanup=None, tentativas: int = 3):
    """Navega com retry quando o Edge/Chrome fica sem recursos temporariamente.

    O erro ERR_INSUFFICIENT_RESOURCES apareceu em lotes grandes porque cada nota
    mantinha formulario + PDF abertos. O retry sozinho nao resolve vazamento de
    abas, mas combinado com o gerenciador de workspaces evita perder o grupo atual.
    """
    ultimo = None
    for tentativa in range(1, max(1, tentativas) + 1):
        try:
            return page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:
            ultimo = exc
            if not erro_recursos_navegador(exc) or tentativa >= tentativas:
                raise
            _log(
                logger,
                f"Navegador com recursos temporariamente insuficientes ao abrir {url}. "
                f"Liberando abas concluidas e tentando novamente ({tentativa}/{tentativas})...",
            )
            try:
                if cleanup:
                    cleanup()
            except Exception:
                pass
            gc.collect()
            try:
                page.wait_for_timeout(1200 * tentativa)
            except Exception:
                time.sleep(1.2 * tentativa)
    if ultimo:
        raise ultimo

DESTINOS_SUPORTADOS = {"nfse", "documentos"}
LOL_CNPJ = "09267506000136"


def resolver_tipo_destino(preferido: str, sugerido: str, dados: Optional[NotaDados] = None) -> str:
    """Resolve a area onde o lancamento atual deve ser preparado.

    A selecao do usuario controla o DESTINO, nao apenas a pesquisa historica.
    Em Automatico, usamos a classificacao do PDF. As notas de debito da LOL
    (09.267.506/0001-36) sao sempre destinadas a Doc. - Contas a pagar.
    """
    preferido = (preferido or "auto").strip().lower()
    sugerido = (sugerido or "nfse").strip().lower()

    if preferido in DESTINOS_SUPORTADOS:
        return preferido

    if dados and _digits(dados.provider_cnpj) == LOL_CNPJ:
        return "documentos"

    if sugerido in DESTINOS_SUPORTADOS:
        return sugerido
    return "nfse"


def _normalizar_numero(valor: str) -> str:
    dig = _digits(valor)
    if not dig:
        return (valor or "").strip().lower()
    try:
        return str(int(dig))
    except Exception:
        return dig.lstrip("0") or "0"


def _linha_documento_atual_corresponde(texto: str, dados: NotaDados) -> bool:
    """Validacao conservadora para localizar um documento ja existente em /documentos."""
    texto_norm = (texto or "").lower()
    if dados.numero and _normalizar_numero(dados.numero) not in {_normalizar_numero(x) for x in re.findall(r"\b[0-9][0-9./-]*\b", texto or "")}:
        if _normalizar_numero(dados.numero) not in _normalizar_numero(texto):
            return False
    if dados.provider_cnpj and _digits(dados.provider_cnpj) not in _digits(texto):
        return False
    if dados.company_cnpj and _digits(dados.company_cnpj) in _digits(texto):
        return True
    if dados.company_name:
        base = dados.company_name.split("(")[0].strip().lower()
        if base and base in texto_norm:
            return True
    # Algumas listas de contas a pagar nao exibem o CNPJ/nome completo da empresa.
    # Se numero + fornecedor conferem, mantemos como candidato.
    return True


def _clicar_acao_documento(page, row) -> bool:
    candidatos = [
        row.get_by_role("button", name=re.compile(r"^(Editar|Ver|Abrir|Completar)$", re.I)),
        row.get_by_role("link", name=re.compile(r"^(Editar|Ver|Abrir|Completar)$", re.I)),
        row.locator(r"button[wire\:click*='open']"),
        row.locator(r"button[wire\:click*='edit']"),
        row.locator(r"a[wire\:click*='open']"),
        row.locator(r"a[wire\:click*='edit']"),
    ]
    for loc in candidatos:
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                return True
        except Exception:
            continue
    return False


def _aguardar_formulario_documentos(page, timeout: int = 9000) -> bool:
    seletores = [
        "#observacao",
        r"textarea[wire\:model*='description']",
        "#file_input",
        "input[type='file']",
    ]
    deadline = datetime.now().timestamp() + timeout / 1000
    while datetime.now().timestamp() < deadline:
        if _primeiro_visivel(page, seletores) is not None:
            return True
        page.wait_for_timeout(120)
    return False


def _preencher_principais_documentos(page, dados: NotaDados, logger: Optional[Logger]) -> None:
    """Preenche campos principais quando o formulario de /documentos os expuser.

    Os seletores sao deliberadamente genericos. Campos inexistentes sao ignorados;
    os complementares (observacao/aprovador/anexo/vencimento) sao obrigatorios quando
    a tela os disponibiliza.
    """
    if dados.company_id:
        empresa = _primeiro_visivel(page, [
            "#empresa",
            r"select[wire\:model*='company_id']",
            r"select[wire\:model*='company']",
        ])
        if empresa is not None:
            try:
                empresa.select_option(str(dados.company_id))
                _aguardar_livewire(page, minimo_ms=180, timeout=3500)
            except Exception:
                pass

    if dados.provider_cnpj:
        try:
            _preencher_cnpj(page, dados.provider_cnpj, dados.provider_name, logger)
        except Exception:
            campo = _primeiro_visivel(page, [
                "#fornecedor",
                r"input[wire\:model*='provider_cnpj']",
                r"input[wire\:model*='supplier_cnpj']",
                r"input[wire\:model*='document']",
            ])
            if campo is not None:
                campo.fill(dados.provider_cnpj)
                _aguardar_livewire(page, minimo_ms=350, timeout=4000)

    campos = [
        (["#numero", r"input[wire\:model*='number']", r"input[wire\:model*='document_number']"], dados.numero),
        (["#valor", r"input[wire\:model*='value']", r"input[wire\:model*='amount']"], dados.valor),
        (["#issued", r"input[wire\:model*='issued_at']", r"input[wire\:model*='issue_date']"], dados.emissao),
    ]
    for seletores, valor in campos:
        if not valor:
            continue
        campo = _primeiro_visivel(page, seletores)
        if campo is not None:
            try:
                campo.fill(str(valor))
            except Exception:
                pass


def _preencher_destino_documentos(page, dados: NotaDados, anexos_pdf: list[str], logger: Optional[Logger]):
    """Prepara o lancamento em Doc. - Contas a pagar sem cair em /nfs.

    Primeiro tenta complementar um documento ja existente. Se nao existir, tenta
    abrir o comando de novo documento usando rotulos comuns do Agilize. Caso a
    tela tenha mudado e nenhum formulario seja reconhecido, mantem /documentos
    aberto e interrompe com mensagem clara — nunca cria NFS-e por engano.
    """
    tipo = TIPOS["documentos"]
    try:
        mesma_rota = str(page.url or "").split("?", 1)[0].rstrip("/") == tipo.url.rstrip("/")
        search_ok = page.locator("#searchInput").count() and page.locator("#searchInput").first.is_visible()
    except Exception:
        mesma_rota = False
        search_ok = False
    if not (mesma_rota and search_ok):
        _navegar_resiliente(page, tipo.url, logger)
    _log(logger, f"Destino do lancamento: {tipo.label}.")

    # 1) Procura o documento atual pelo numero/fatura, se a lista expuser pesquisa.
    try:
        search = page.locator("#searchInput")
        if search.count() and search.first.is_visible() and dados.numero:
            for label in ("Número", "Numero", "Documento"):
                if _select_if_exists(page, "#searchType", label_contains=label):
                    break
            search.first.fill(str(dados.numero))
            _aguardar_pesquisa_livewire(page, minimo_ms=1600, timeout=6500)
            rows = page.locator("tbody tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                try:
                    texto = row.inner_text().strip()
                except Exception:
                    continue
                if not _linha_documento_atual_corresponde(texto, dados):
                    continue
                if _clicar_acao_documento(page, row):
                    if _aguardar_formulario_documentos(page, timeout=10000):
                        _log(logger, f"Documento {dados.numero} existente localizado em {tipo.label}; complementando o registro.")
                        _preencher_campos_complementares(page, dados, anexos_pdf, logger, "documento existente")
                        return "documento_existente"
    except Exception as exc:
        _log(logger, f"Pesquisa do documento atual em {tipo.label} nao concluiu: {exc}")

    # 2) Se nao existe, tenta abrir um formulario novo na area correta.
    nomes = [
        "Enviar Documento",
        "Novo Documento",
        "Adicionar Documento",
        "Cadastrar Documento",
        "Novo lançamento",
        "Novo lancamento",
    ]
    for nome in nomes:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(nome), re.I))
            if not btn.count():
                btn = page.get_by_role("link", name=re.compile(re.escape(nome), re.I))
            if btn.count() and btn.first.is_visible():
                btn.first.click()
                if _aguardar_formulario_documentos(page, timeout=10000):
                    _log(logger, f"Formulario de {tipo.label} aberto.")
                    _preencher_principais_documentos(page, dados, logger)
                    _preencher_campos_complementares(page, dados, anexos_pdf, logger, "Doc. - Contas a pagar")
                    return "documento_novo"
        except Exception:
            continue

    raise RuntimeError(
        "O destino correto e 'Doc. - Contas a pagar', e a automacao manteve essa area aberta. "
        "Porem o formulario atual de /documentos nao foi reconhecido pelos seletores mapeados. "
        "A NFS-E NAO sera usada como contingencia. Capture um HAR apenas da abertura do novo documento "
        "em Doc. - Contas a pagar para completar esse mapeamento."
    )


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


def _subtrair_meses(data_base: date, meses: int) -> date:
    """Subtrai meses de calendario preservando o dia quando possivel."""
    total = data_base.year * 12 + (data_base.month - 1) - max(0, meses)
    ano = total // 12
    mes = total % 12 + 1
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def _intervalo_historico(tipo_key: str, dados: NotaDados) -> tuple[str, str]:
    """Retorna o periodo usado na pesquisa de historico.

    - NFS-E: tres meses completos anteriores ao mes da nota atual.
      Isso cobre o mes anterior + dois meses extras e evita perder referencias
      validas que ficaram fora por poucos dias.
    - Doc. - Contas a pagar: janela movel dos ultimos dois meses ate hoje.
    """
    if tipo_key == "documentos":
        hoje = date.today()
        inicio = _subtrair_meses(hoje, 2)
        return inicio.isoformat(), hoje.isoformat()
    return _intervalo_historico_nfse(dados.emissao)


def _preencher_intervalo_historico(page, tipo_key: str, dados: NotaDados, logger: Optional[Logger]) -> tuple[str, str]:
    inicio, fim = _intervalo_historico(tipo_key, dados)

    start_selectors = [
        r'input[wire\:model\.debounce\.1000ms="filter.dateStart"]',
        r'input[wire\:model*="dateStart"]',
        r'input[wire\:model*="startDate"]',
    ]
    end_selectors = [
        r'input[wire\:model\.debounce\.1000ms="filter.dateEnd"]',
        r'input[wire\:model*="dateEnd"]',
        r'input[wire\:model*="endDate"]',
    ]

    start_ok = _fill_if_exists(page, start_selectors, inicio)
    end_ok = _fill_if_exists(page, end_selectors, fim)

    # Fallback para telas que usam outro wire:model, mas mantem dois campos date.
    if not (start_ok and end_ok):
        try:
            dates = page.locator('input[type="date"]:visible')
            if dates.count() >= 2:
                if not start_ok:
                    dates.nth(0).fill(inicio)
                    start_ok = True
                if not end_ok:
                    dates.nth(1).fill(fim)
                    end_ok = True
        except Exception:
            pass

    if start_ok or end_ok:
        # Os campos usam debounce. Aguarda antes de preencher a pesquisa para nao
        # consultar o fornecedor ainda com o filtro padrao do dia atual.
        _aguardar_livewire(page, minimo_ms=1550, timeout=7000)

    # Confere o que ficou efetivamente na tela para TODAS as areas. O Livewire
    # pode reconstruir os inputs e restaurar a data padrao depois de empresa,
    # status ou tipo de busca. Se isso ocorrer, reaplicamos uma vez.
    try:
        dates = page.locator('input[type="date"]:visible')
        if dates.count() >= 2:
            atual_inicio = dates.nth(0).input_value().strip()
            atual_fim = dates.nth(1).input_value().strip()
            if atual_inicio != inicio or atual_fim != fim:
                dates.nth(0).fill(inicio)
                dates.nth(1).fill(fim)
                _aguardar_livewire(page, minimo_ms=1550, timeout=7000)
                atual_inicio = dates.nth(0).input_value().strip()
                atual_fim = dates.nth(1).input_value().strip()
            _log(logger, f"{TIPOS[tipo_key].label}: datas confirmadas na tela = {atual_inicio} ate {atual_fim}.")
    except Exception as exc:
        _log(logger, f"{TIPOS[tipo_key].label}: nao foi possivel confirmar visualmente os campos de data: {exc}")

    if tipo_key == "documentos":
        _log(logger, f"{TIPOS[tipo_key].label}: periodo de pesquisa ajustado para {inicio} ate {fim} (ultimos 2 meses).")
    else:
        _log(
            logger,
            f"{TIPOS[tipo_key].label}: periodo de pesquisa ajustado para {inicio} ate {fim} "
            "(3 meses completos anteriores: mes anterior + 2 meses extras).",
        )
    return inicio, fim


def _abrir_edicao_e_ler(page, row, logger: Optional[Logger]) -> tuple[str, str]:
    # Compatibilidade com a atualização do Agilize (set/2026): a lista deixou de
    # emitir edit-nfs diretamente e passou a usar button -> openNfsModal(id) ->
    # evento openModal. O helper compartilhado aguarda a segunda etapa Livewire e
    # le a observacao do estado inicial do componente, sem depender do tempo do textarea.
    if not _abrir_modal_edicao(page, row, logger):
        return "", ""

    obs, aprovador = _ler_dados_modal_edicao(page, logger)
    _fechar_modal_sem_salvar(page)
    return obs, aprovador


def _buscar_em_tipo(page, dados: NotaDados, tipo_key: str, logger: Optional[Logger]):
    tipo = TIPOS[tipo_key]
    if tipo_key == "documentos":
        _log(logger, f"Pesquisando fornecedor por NOME em {tipo.label}...")
    else:
        _log(logger, f"Pesquisando fornecedor por CNPJ em {tipo.label}...")

    _navegar_resiliente(page, tipo.url, logger)
    try:
        page.locator("#searchInput").wait_for(state="visible", timeout=9000)
    except PlaywrightTimeoutError:
        _log(logger, f"{tipo.label}: tela de pesquisa diferente do mapeamento atual.")
        return None

    # Resolve a empresa pelo ID conhecido ou, se a filial acabou de ser cadastrada,
    # pelo CNPJ/nome exibido nas options do proprio Agilize.
    _selecionar_empresa_por_dados(
        page,
        dados,
        [
            "#underline_select",
            r"select[wire\:model*='company']",
            "select[id*='empresa']",
            "select[id*='company']",
        ],
        logger,
        f"historico em {tipo.label}",
    )

    # A chave de pesquisa historica depende da area:
    # - Notas NFS-E: CNPJ/documento do fornecedor (mais preciso nessa grade).
    # - Doc. - Contas a pagar: NOME do fornecedor/beneficiario. Nesta tela o
    #   numero da nota/fatura e apenas referencia do titulo e nao deve conduzir
    #   a busca da observacao. Ex.: LOL SERVICOS DE INTERNET LTDA.
    if tipo_key == "documentos":
        fornecedor_busca = (dados.provider_name or dados.beneficiario_nome or "").strip()
        if not fornecedor_busca:
            _log(logger, f"{tipo.label}: nome do fornecedor nao identificado para pesquisa historica.")
            return None

        selecionou_nome = False
        for label in ("Nome fornecedor", "Fornecedor", "Beneficiário", "Beneficiario", "Nome"):
            if _select_if_exists(page, "#searchType", label_contains=label):
                selecionou_nome = True
                _aguardar_livewire(page, minimo_ms=350, timeout=4000)
                break
        if not selecionou_nome:
            # Busca geral continua recebendo o NOME. Nunca substitui por CNPJ nesta area.
            _log(logger, f"{tipo.label}: filtro por nome nao identificado; usando busca geral PELO NOME do fornecedor.")

        valor_busca = fornecedor_busca
        _log(logger, f"{tipo.label}: valor de busca historica = '{fornecedor_busca}' (nome do fornecedor).")
    else:
        if not _select_if_exists(page, "#searchType", label_contains="Documento fornecedor"):
            if not _select_if_exists(page, "#searchType", label_contains="CNPJ"):
                _select_if_exists(page, "#searchType", label_contains="Documento")
        valor_busca = dados.provider_cnpj

        # Na lista de NFS-e, historico valido para copiar observacao/aprovador deve
        # estar com Situacao de Entrada = Efetuada. Evita usar registros "Nao possui".
        _selecionar_status_efetuada(page, logger)

    # Datas ficam por ultimo, imediatamente antes da pesquisa. Isso evita que uma
    # troca de empresa/tipo de busca no Livewire restaure o filtro padrao da tela.
    inicio, fim = _preencher_intervalo_historico(page, tipo_key, dados, logger)

    search_input = page.locator("#searchInput")
    search_input.fill(valor_busca)
    _aguardar_pesquisa_livewire(page, minimo_ms=1800 if tipo_key == "nfse" else 1700, timeout=7500)

    # Livewire pode recriar o input ao alterar o tipo de pesquisa. Confirma o valor
    # e reaplica uma vez para impedir que a tela volte para um valor anterior/CNPJ.
    if tipo_key == "documentos":
        try:
            atual = page.locator("#searchInput").input_value().strip()
        except Exception:
            atual = ""
        if atual != valor_busca:
            page.locator("#searchInput").fill(valor_busca)
            _aguardar_pesquisa_livewire(page, minimo_ms=1650, timeout=7000)
        _log(logger, f"{tipo.label}: campo Buscar confirmado com o nome '{valor_busca}'.")

    rows = page.locator("tbody tr")
    candidatos: list[tuple[datetime, int, str, str]] = []
    provider_digits = _digits(dados.provider_cnpj)
    provider_name = (dados.provider_name or dados.beneficiario_nome or "").strip().lower()
    company_digits = _digits(dados.company_cnpj)
    company_name = (dados.company_name or "").lower()

    for i in range(rows.count()):
        row = rows.nth(i)
        try:
            text = row.inner_text().strip()
        except Exception:
            continue
        if tipo_key == "nfse":
            if provider_digits and provider_digits not in _digits(text):
                continue
        else:
            # Em Contas a pagar, a pesquisa foi feita pelo nome do fornecedor.
            # Confirma o nome quando ele estiver exposto na linha; se a grade
            # também expuser CNPJ, aceita a confirmacao por CNPJ.
            text_lower = text.lower()
            nome_ok = bool(provider_name and provider_name in text_lower)
            cnpj_ok = bool(provider_digits and provider_digits in _digits(text))
            if provider_name and not nome_ok and not cnpj_ok:
                continue
        dt, dt_text = _primeira_data(text)
        numero = ""
        cells = row.locator("th, td")
        try:
            values = [c.strip() for c in cells.all_inner_texts()]
            if len(values) > 1:
                numero = values[1]
        except Exception:
            values = []

        if tipo_key == "nfse":
            if values and not _linha_mesma_empresa(values, dados):
                empresa_txt = values[4] if len(values) > 4 else "outra empresa"
                _log(logger, f"{tipo.label}: ignorando historico de outra empresa: {empresa_txt}")
                continue
            if not _linha_nfs_efetuada(values):
                situacao_txt = values[8] if len(values) > 8 else "nao identificada"
                _log(logger, f"{tipo.label}: ignorando {numero or 'registro'} com Situacao de Entrada = {situacao_txt}; esperado Efetuada.")
                continue
        else:
            # Em outras telas, quando houver CNPJ/nome da empresa no texto, usa-o
            # como validacao complementar sem impor o layout especifico de /nfs.
            if company_digits and company_digits in _digits(text):
                company_ok = True
            elif company_name and company_name.split("(")[0].strip().lower() in text.lower():
                company_ok = True
            else:
                company_ok = True
            if not company_ok:
                continue

        candidatos.append((dt, i, numero, dt_text))

    if not candidatos:
        if tipo_key == "documentos":
            _log(logger, f"{tipo.label}: nenhum registro do fornecedor encontrado entre {inicio} e {fim}.")
        else:
            _log(logger, f"{tipo.label}: nenhum registro para o CNPJ entre {inicio} e {fim}.")
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
    if not dados.company_id and not dados.company_cnpj and not dados.company_name:
        _log(logger, "Pesquisa de referencia: empresa nao identificada.")
        return None
    if not dados.provider_cnpj and not dados.provider_name and not dados.beneficiario_nome:
        _log(logger, "Pesquisa de referencia: fornecedor nao identificado.")
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
        _log(logger, f"{found.get('tipo_label')}: fornecedor localizado, mas sem dados reutilizaveis; continuando a pesquisa.")
    if primeiro_registro:
        _log(logger, "Fornecedor localizado no historico, porem sem observacao/aprovador reutilizavel nas telas mapeadas.")
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
        self._context_closed = False
        # v0.9.6: processamento propositalmente sequencial.
        # Mantemos apenas UM lançamento preparado por vez para evitar
        # ERR_INSUFFICIENT_RESOURCES em lotes grandes.
        # O nome AUTOMACAO_AGILIZE_MAX_ABERTOS e mantido apenas como
        # referencia de compatibilidade documental da v0.9.5; nao altera
        # mais o comportamento da fila.
        self.max_workspaces = 1
        self._workspaces: list[dict] = []
        self._historico_cache: dict[tuple, dict | None] = {}

    def _formulario_ativo(self, page) -> bool:
        if page is None:
            return False
        try:
            if page.is_closed():
                return False
        except Exception:
            return False
        seletores = [
            "#observacao",
            r"textarea[wire\:model*='description']",
            "#file_input",
            "input[type='file']",
            r"input[wire\:model*='due']",
            r"input[wire\:model*='expiration']",
        ]
        for selector in seletores:
            try:
                loc = page.locator(selector)
                if loc.count() and loc.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    def _fechar_workspace(self, ws: dict) -> None:
        for key in ("pdf", "page"):
            pg = ws.get(key)
            try:
                if pg is not None and not pg.is_closed():
                    pg.close()
            except Exception:
                pass

    def _limpar_workspaces_concluidos(self) -> int:
        mantidos: list[dict] = []
        liberados = 0
        for ws in self._workspaces:
            page = ws.get("page")
            if self._formulario_ativo(page):
                mantidos.append(ws)
                continue
            liberados += 1
            numero = ws.get("numero") or "(sem referencia)"
            self._fechar_workspace(ws)
            _log(self.logger, f"Liberando abas do lancamento {numero} ja concluido/fechado.")
        self._workspaces = mantidos
        return liberados

    def _aguardar_capacidade(self) -> None:
        avisou = False
        while True:
            self._limpar_workspaces_concluidos()
            if len(self._workspaces) < self.max_workspaces:
                return
            if not avisou:
                _log(
                    self.logger,
                    "Limite seguro sequencial: a Automacao Agilize prepara apenas 1 lancamento por vez. "
                    "Envie, cancele ou feche o formulario atual para liberar automaticamente o proximo da fila. "
                    "Essa regra evita ERR_INSUFFICIENT_RESOURCES em lotes grandes.",
                )
                avisou = True
            time.sleep(1.0)

    def _nova_pagina(self):
        assert self.context is not None
        ultimo = None
        for tentativa in range(1, 4):
            try:
                return self.context.new_page()
            except Exception as exc:
                ultimo = exc
                if not erro_recursos_navegador(exc) or tentativa >= 3:
                    raise
                self._limpar_workspaces_concluidos()
                gc.collect()
                _log(self.logger, f"Recursos do navegador no limite ao abrir nova aba. Tentativa {tentativa}/3...")
                time.sleep(1.2 * tentativa)
        if ultimo:
            raise ultimo

    def _context_ativo(self) -> bool:
        if self.context is None or self._context_closed:
            return False
        try:
            # cookies() faz uma chamada real ao browser e detecta contextos mortos.
            self.context.cookies()
            return True
        except Exception:
            return False

    def open(self, force_reopen: bool = False):
        if force_reopen:
            self.close()
        if self._context_ativo():
            return
        if self.context is not None:
            self.close()
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
        self._context_closed = False
        try:
            self.context.on("close", lambda: setattr(self, "_context_closed", True))
        except Exception:
            pass

    def _ensure_login(self, page):
        _navegar_resiliente(page, AGILIZE_URL, self.logger, cleanup=self._limpar_workspaces_concluidos)
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
        self._aguardar_capacidade()
        try:
            page = self._nova_pagina()
        except Exception as exc:
            if not erro_navegador_fechado(exc):
                raise
            _log(self.logger, "O navegador/contexto foi encerrado antes de abrir o lancamento. Recriando a sessao...")
            self.open(force_reopen=True)
            assert self.context is not None
            self._aguardar_capacidade()
            page = self._nova_pagina()
        page.set_default_timeout(15000)
        self._ensure_login(page)

        # Resolve o destino ANTES da pesquisa historica.
        destino = resolver_tipo_destino(tipo_preferido, tipo_sugerido, dados)
        _log(self.logger, f"Destino resolvido antes da pesquisa historica: {TIPOS[destino].label}.")

        # v0.9.8: antes de gastar tempo procurando observacao do mes anterior,
        # verifica a nota atual. Se ela ja estiver Aguardando Aprovacao/Efetuada,
        # o trabalho terminou e a fila pode seguir imediatamente.
        precheck = ...
        if destino == "nfse":
            precheck = _localizar_registro_existente(page, dados, self.logger)
            if precheck and _status_ja_processado(str(precheck.get("situacao") or "")):
                situacao = str(precheck.get("situacao") or "")
                _log(
                    self.logger,
                    f"Lancamento {dados.numero} ja esta em '{situacao}'. Historico/anexos nao serao reprocessados; seguindo para o proximo item.",
                )
                try:
                    page.close()
                except Exception:
                    pass
                return {"state": "ja_processado", "situacao": situacao}

        # Cache seguro por fornecedor + empresa + mes anterior. Quando varios
        # documentos compartilham a mesma referencia historica, evita repetir a
        # mesma navegacao/abertura de modal.
        inicio_hist, _fim_hist = _intervalo_historico(destino, dados)
        cache_key = (
            destino,
            re.sub(r"\D", "", dados.provider_cnpj or "") or (dados.provider_name or dados.beneficiario_nome or "").strip().lower(),
            re.sub(r"\D", "", dados.company_cnpj or "") or str(dados.company_id or "") or (dados.company_name or "").strip().lower(),
            inicio_hist[:7],
        )
        if cache_key in self._historico_cache:
            referencia = self._historico_cache[cache_key]
            if referencia:
                _log(self.logger, f"Referencia historica reutilizada em cache: {referencia.get('tipo_label')} {referencia.get('numero') or ''}".strip())
        else:
            referencia = buscar_referencia_multitipo(page, dados, destino, destino, self.logger)
            self._historico_cache[cache_key] = referencia

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

        _log(self.logger, f"Area selecionada para o lancamento: {TIPOS[destino].label}.")
        if referencia and referencia.get("tipo") != destino:
            _log(
                self.logger,
                f"A referencia historica veio de {referencia.get('tipo_label')}, mas o destino do lancamento "
                f"permanece {TIPOS[destino].label}.",
            )

        if destino == "documentos":
            resultado_destino = _preencher_destino_documentos(page, dados, anexos_pdf, self.logger)
        else:
            # Nao recarrega /nfs aqui. _preencher_destino sabe reaproveitar a
            # lista atual e so navega quando realmente necessario.
            resultado_destino = _preencher_destino(page, dados, anexos_pdf, self.logger, precheck=precheck)

        if resultado_destino == "ja_processado":
            try:
                page.close()
            except Exception:
                pass
            return {"state": "ja_processado", "situacao": str((precheck or {}).get("situacao") or "")}

        pdf_page = None
        if conferencia_pdf:
            try:
                pdf_page = self._nova_pagina()
                _navegar_resiliente(pdf_page, Path(conferencia_pdf).resolve().as_uri(), self.logger, tentativas=2)
            except Exception as exc:
                # PDF de conferencia e auxiliar. Nao marca o lancamento inteiro como erro
                # quando o Chromium esta sob pressao; o formulario preenchido continua valido.
                _log(self.logger, f"Nao foi possivel abrir o PDF de conferencia automaticamente: {exc}")
                try:
                    if pdf_page is not None and not pdf_page.is_closed():
                        pdf_page.close()
                except Exception:
                    pass
                pdf_page = None

        self._workspaces.append({"page": page, "pdf": pdf_page, "numero": dados.numero})
        page.bring_to_front()
        _log(
            self.logger,
            f"Lançamento {dados.numero or '(sem referência)'} preparado. "
            "Modo sequencial: 1 por vez. O envio continua manual; ao concluir/fechar este, o proximo sera liberado.",
        )
        return {"state": "aberto", "page": page}

    def close(self):
        for ws in list(self._workspaces):
            self._fechar_workspace(ws)
        self._workspaces = []
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        self.context = None
        self._context_closed = True
        try:
            if self._p:
                self._p.stop()
        except Exception:
            pass
        self._p = None
