from __future__ import annotations

import html
import json
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




def _normalizar_texto(valor: str) -> str:
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto).strip().lower()


def _selecionar_status_efetuada(page, logger: Optional[Logger] = None) -> bool:
    """Forca a pesquisa historica de NFS-e para Situacao de Entrada = Efetuada.

    O Agilize atual usa #status / filter.status, com valor 99 para Efetuada.
    A funcao prioriza o rotulo para tolerar eventual mudanca do valor interno e
    usa 99 como compatibilidade com a versao atual.
    """
    try:
        status = page.locator("#status")
        if not status.count() or not status.first.is_visible():
            _log(logger, "Filtro de situacao nao localizado; a linha sera validada como Efetuada antes de ser usada.")
            return False

        options = status.first.locator("option")
        for i in range(options.count()):
            opt = options.nth(i)
            texto = _normalizar_texto(opt.inner_text())
            if texto == "efetuada":
                valor = opt.get_attribute("value") or "99"
                status.first.select_option(valor)
                _log(logger, "Filtro de historico: Situacao de Entrada = Efetuada.")
                return True

        status.first.select_option("99")
        _log(logger, "Filtro de historico: Situacao de Entrada = Efetuada (99).")
        return True
    except Exception as exc:
        _log(logger, f"Nao foi possivel aplicar o filtro Efetuada: {exc}. A linha sera validada antes de ser usada.")
        return False


def _linha_nfs_efetuada(cells: list[str]) -> bool:
    """Valida a coluna Situacao de Entrada da lista de NFS-e.

    Layout atual: checkbox, numero, valor, emissao, empresa, CNPJ, fornecedor,
    vencimento, situacao, aprovador, anexo, acao. Mantemos fallback textual
    caso a tabela mude levemente de ordem.
    """
    if len(cells) > 8:
        situacao = _normalizar_texto(cells[8])
        if situacao:
            return situacao == "efetuada"
    return any(_normalizar_texto(c) == "efetuada" for c in cells)


def _linha_nfs_nao_possui(cells: list[str]) -> bool:
    """Identifica o novo estado de NFS-e importada ainda nao complementada."""
    if len(cells) > 8:
        situacao = _normalizar_texto(cells[8])
        if situacao:
            return situacao == "nao possui"
    return any(_normalizar_texto(c) == "nao possui" for c in cells)


def _normalizar_numero_nota(valor: str) -> str:
    bruto = str(valor or "").strip()
    digitos = re.sub(r"\D", "", bruto)
    if not digitos:
        return _normalizar_texto(bruto)
    try:
        return str(int(digitos))
    except Exception:
        return digitos.lstrip("0") or "0"


def _numero_nota_com_prefixo_indevido(numero_linha: str, numero_esperado: str) -> bool:
    """Reconhece o caso em que o Agilize pre-cadastrou um prefixo indevido.

    Exemplo real: PDF/NFS-e 2721 e registro importado 2600000002721.
    Esta equivalencia nunca e usada sozinha: o fallback que a consome exige
    empresa, fornecedor, valor e emissao compativeis antes de reutilizar a linha.
    """
    linha = _normalizar_numero_nota(numero_linha)
    esperado = _normalizar_numero_nota(numero_esperado)
    if not linha or not esperado or linha == esperado:
        return False
    if not linha.isdigit() or not esperado.isdigit():
        return False
    if len(esperado) < 3:
        return False

    # Evita considerar uma nota apenas um pouco maior como equivalente
    # (ex.: 12721 x 2721). O erro observado acrescenta um bloco de controle
    # antes do numero fiscal, por isso exigimos ao menos 4 digitos extras.
    if len(linha) - len(esperado) < 4:
        return False
    return linha.endswith(esperado)


def _normalizar_valor_centavos(valor: str):
    texto = str(valor or "").strip()
    if not texto:
        return None
    texto = re.sub(r"[^0-9,.-]", "", texto)
    try:
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        return int(round(float(texto) * 100))
    except Exception:
        return None


def _data_br_iso(valor_iso: str) -> str:
    try:
        return datetime.strptime(str(valor_iso or ""), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return ""


def _linha_importada_corresponde(cells: list[str], dados: NotaDados) -> tuple[bool, str]:
    """Confirma que a linha 'Nao possui' e exatamente a nota atual importada.

    Nao basta o numero: validamos empresa/filial, CNPJ do fornecedor e, quando
    disponiveis, valor e emissao. Isso evita alimentar um registro homonimo.
    """
    if len(cells) < 9:
        return False, "linha incompleta"
    if not _linha_nfs_nao_possui(cells):
        return False, f"situacao {cells[8] if len(cells) > 8 else 'desconhecida'}"

    numero_linha = _normalizar_numero_nota(cells[1] if len(cells) > 1 else "")
    numero_dados = _normalizar_numero_nota(dados.numero)
    if numero_dados and numero_linha != numero_dados:
        return False, f"numero {cells[1]}"

    if not _linha_mesma_empresa(cells, dados):
        return False, f"empresa {cells[4] if len(cells) > 4 else ''}"

    if dados.provider_cnpj and len(cells) > 5:
        if re.sub(r"\D", "", dados.provider_cnpj) != re.sub(r"\D", "", cells[5]):
            return False, f"CNPJ fornecedor {cells[5]}"

    esperado_valor = _normalizar_valor_centavos(dados.valor)
    linha_valor = _normalizar_valor_centavos(cells[2] if len(cells) > 2 else "")
    if esperado_valor is not None and linha_valor is not None and esperado_valor != linha_valor:
        return False, f"valor {cells[2]}"

    esperado_emissao = _data_br_iso(dados.emissao)
    linha_emissao = (cells[3] if len(cells) > 3 else "").strip()
    if esperado_emissao and linha_emissao and esperado_emissao != linha_emissao:
        return False, f"emissao {linha_emissao}"

    return True, ""


def _linha_importada_prefixada_corresponde(cells: list[str], dados: NotaDados) -> tuple[bool, str]:
    """Valida uma NFS-e atual cujo numero foi pre-cadastrado com prefixo indevido.

    O numero por sufixo e apenas uma evidencia inicial. Para evitar abrir uma
    nota errada, empresa, fornecedor, valor e emissao precisam conferir.
    """
    if len(cells) < 9:
        return False, "linha incompleta"

    numero_linha = cells[1] if len(cells) > 1 else ""
    if not _numero_nota_com_prefixo_indevido(numero_linha, dados.numero):
        return False, f"numero {numero_linha}"

    if not _linha_mesma_empresa(cells, dados):
        return False, f"empresa {cells[4] if len(cells) > 4 else ''}"

    if dados.provider_cnpj:
        if len(cells) <= 5 or re.sub(r"\D", "", dados.provider_cnpj) != re.sub(r"\D", "", cells[5]):
            return False, f"CNPJ fornecedor {cells[5] if len(cells) > 5 else ''}"
    else:
        esperado_nome = _normalizar_texto(dados.provider_name or "")
        linha_nome = _normalizar_texto(cells[6] if len(cells) > 6 else "")
        if not esperado_nome or esperado_nome not in linha_nome:
            return False, f"fornecedor {cells[6] if len(cells) > 6 else ''}"

    esperado_valor = _normalizar_valor_centavos(dados.valor)
    linha_valor = _normalizar_valor_centavos(cells[2] if len(cells) > 2 else "")
    if esperado_valor is None or linha_valor is None or esperado_valor != linha_valor:
        return False, f"valor {cells[2] if len(cells) > 2 else ''}"

    esperado_emissao = _data_br_iso(dados.emissao)
    linha_emissao = (cells[3] if len(cells) > 3 else "").strip()
    if not esperado_emissao or not linha_emissao or esperado_emissao != linha_emissao:
        return False, f"emissao {linha_emissao}"

    return True, ""


def _linha_atual_confirmada(cells: list[str], dados: NotaDados) -> bool:
    """Confirma identidade completa antes de reaproveitar registro de outra area.

    Numero/sufixo sozinho nao basta. Nao altera a pontuacao historica usada na
    pesquisa tradicional, mas impede redirecionar Contas a pagar para uma
    NFS-e homonima de outro fornecedor, empresa ou competencia.
    """
    if len(cells) < 9 or not cells[4].strip():
        return False
    if not (dados.company_name or dados.company_cnpj):
        return False
    if not _linha_mesma_empresa(cells, dados):
        return False
    cnpj_empresa = re.sub(r"\D", "", dados.company_cnpj or "")
    if len(cnpj_empresa) == 14:
        filial = cnpj_empresa[-6:-2] + "-" + cnpj_empresa[-2:]
        filial_linha = re.search(r"\((\d{4}-\d{2})\)", cells[4])
        if filial_linha and filial_linha.group(1) != filial:
            return False
        if not dados.company_name and cnpj_empresa not in re.sub(r"\D", "", cells[4]) and filial not in cells[4]:
            return False

    cnpj = re.sub(r"\D", "", dados.provider_cnpj or "")
    if not cnpj or cnpj != re.sub(r"\D", "", cells[5]):
        return False
    esperado = _normalizar_valor_centavos(dados.valor)
    if esperado is None or esperado != _normalizar_valor_centavos(cells[2]):
        return False
    emissao = _data_br_iso(dados.emissao)
    if not emissao or cells[3].strip() != emissao:
        return False
    return (
        _normalizar_numero_nota(cells[1]) == _normalizar_numero_nota(dados.numero)
        or _numero_nota_com_prefixo_indevido(cells[1], dados.numero)
    )


def _selecionar_status_nao_possui(page, logger: Optional[Logger] = None) -> bool:
    """Seleciona o status novo -1 / 'Nao possui' para localizar nota importada."""
    try:
        status = page.locator("#status")
        if not status.count() or not status.first.is_visible():
            return False
        options = status.first.locator("option")
        for i in range(options.count()):
            opt = options.nth(i)
            if _normalizar_texto(opt.inner_text()) == "nao possui":
                status.first.select_option(opt.get_attribute("value") or "-1")
                _log(logger, "Pesquisa da nota atual: Situacao de Entrada = Nao possui.")
                return True
        status.first.select_option("-1")
        _log(logger, "Pesquisa da nota atual: Situacao de Entrada = Nao possui (-1).")
        return True
    except Exception:
        return False




def _selecionar_status_todos(page, logger: Optional[Logger] = None) -> bool:
    """Remove a restricao de Situacao de Entrada ao procurar a nota atual.

    A regra de duplicidade agora e simples: se o mesmo numero de NFS-e ja existe
    no Agilize, o registro existente deve ser aberto em Editar/Ver nota. Somente
    quando nenhuma linha com o numero for encontrada o fluxo pode criar uma nova.
    """
    try:
        status = page.locator("#status")
        if not status.count() or not status.first.is_visible():
            _log(logger, "Filtro de situacao nao localizado; pesquisando o numero sem depender do status visual.")
            return False
        options = status.first.locator("option")
        for i in range(options.count()):
            opt = options.nth(i)
            texto = _normalizar_texto(opt.inner_text())
            if "todos" in texto:
                valor = opt.get_attribute("value") or "9999"
                status.first.select_option(valor)
                _log(logger, "Pesquisa da nota atual: Situacao de Entrada = Todos os status.")
                return True
        # Compatibilidade com o Agilize atual, onde 9999 representa todos os status.
        status.first.select_option("9999")
        _log(logger, "Pesquisa da nota atual: Situacao de Entrada = Todos os status (9999).")
        return True
    except Exception as exc:
        _log(logger, f"Nao foi possivel selecionar Todos os status: {exc}. A busca pelo numero continuara.")
        return False


def _status_ja_processado(situacao: str) -> bool:
    """Status em que o registro ja foi enviado e nao deve ser reprocessado.

    Aguardando Aprovacao e Efetuada nao expoem necessariamente Anexo/Editar.
    Tratar esses registros como erro fazia o lote repetir trabalho ja concluido.
    """
    normal = _normalizar_texto(situacao)
    return normal in {"aguardando aprovacao", "efetuada"}


def _garantir_lista_nfs(page, timeout: int = 15000) -> None:
    """Mantem a pagina atual quando /nfs ja esta pronta, evitando reload caro."""
    try:
        mesma_rota = str(page.url or "").split("?", 1)[0].rstrip("/") == AGILIZE_URL.rstrip("/")
        search = page.locator("#searchInput")
        modal = page.locator("#modal-container")
        modal_visivel = bool(modal.count() and modal.first.is_visible())
        if mesma_rota and search.count() and search.first.is_visible() and not modal_visivel:
            return
    except Exception:
        pass
    page.goto(AGILIZE_URL, wait_until="domcontentloaded")
    _esperar_lista(page, timeout=timeout)


def _score_linha_mesmo_numero(cells: list[str], dados: NotaDados) -> tuple[int, list[str]]:
    """Pontua uma linha que ja possui exatamente o mesmo numero da nota.

    O numero e requisito obrigatorio. Empresa, fornecedor, valor e emissao servem
    para escolher o melhor registro quando houver mais de uma linha homonima.
    Nunca usamos status como bloqueio para a nota atual.
    """
    if len(cells) < 2:
        return -1, ["linha incompleta"]
    if _normalizar_numero_nota(cells[1]) != _normalizar_numero_nota(dados.numero):
        return -1, [f"numero {cells[1] if len(cells) > 1 else ''}"]

    score = 100
    motivos: list[str] = []

    if _linha_mesma_empresa(cells, dados):
        score += 50
    else:
        motivos.append(f"empresa diferente: {cells[4] if len(cells) > 4 else ''}")

    if dados.provider_cnpj and len(cells) > 5:
        if re.sub(r"\D", "", dados.provider_cnpj) == re.sub(r"\D", "", cells[5]):
            score += 35
        else:
            motivos.append(f"CNPJ fornecedor diferente: {cells[5]}")

    esperado_valor = _normalizar_valor_centavos(dados.valor)
    linha_valor = _normalizar_valor_centavos(cells[2] if len(cells) > 2 else "")
    if esperado_valor is not None and linha_valor is not None:
        if esperado_valor == linha_valor:
            score += 15
        else:
            motivos.append(f"valor diferente: {cells[2]}")

    esperado_emissao = _data_br_iso(dados.emissao)
    linha_emissao = (cells[3] if len(cells) > 3 else "").strip()
    if esperado_emissao and linha_emissao:
        if esperado_emissao == linha_emissao:
            score += 10
        else:
            motivos.append(f"emissao diferente: {linha_emissao}")

    # Entre candidatos equivalentes, prefira o registro ainda nao complementado,
    # mas qualquer status continua elegivel para edicao.
    if _linha_nfs_nao_possui(cells):
        score += 5

    return score, motivos

def _selecionar_empresa_por_dados(page, dados: NotaDados, selectors: list[str], logger: Optional[Logger] = None, contexto: str = "lista") -> bool:
    """Seleciona a empresa pelo ID conhecido ou resolve o ID pelo proprio select.

    O mapa local continua sendo o caminho mais rapido, mas o Agilize pode cadastrar
    uma filial nova antes de a automacao ser atualizada. Se houver CNPJ/nome nos
    dados extraidos do PDF, procuramos a option correspondente e guardamos o ID
    encontrado para o restante do fluxo.
    """
    alvo = _primeiro_visivel(page, selectors)
    if alvo is None:
        return False

    if dados.company_id:
        try:
            alvo.select_option(str(dados.company_id))
            _aguardar_livewire(page, minimo_ms=220, timeout=4000)
            return True
        except Exception:
            pass

    cnpj_digits = re.sub(r"\D", "", dados.company_cnpj or "")
    nome_base = _normalizar_texto((dados.company_name or "").split("(", 1)[0]).strip()
    try:
        options = alvo.locator("option")
        for i in range(options.count()):
            opt = options.nth(i)
            texto = (opt.inner_text() or "").strip()
            valor = (opt.get_attribute("value") or "").strip()
            if not valor or valor == "0":
                continue
            texto_digits = re.sub(r"\D", "", texto)
            texto_norm = _normalizar_texto(texto)
            cnpj_ok = bool(cnpj_digits and cnpj_digits in texto_digits)
            nome_ok = bool(nome_base and nome_base in texto_norm)
            if not cnpj_ok and not nome_ok:
                continue
            alvo.select_option(valor)
            try:
                dados.company_id = int(valor)
            except Exception:
                pass
            if not dados.company_name:
                dados.company_name = texto
            _aguardar_livewire(page, minimo_ms=220, timeout=4000)
            _log(logger, f"Empresa resolvida pelo proprio Agilize no {contexto}: {texto} (id {valor}).")
            return True
    except Exception:
        return False
    return False


def _linha_mesma_empresa(cells: list[str], dados: NotaDados) -> bool:
    if len(cells) <= 4:
        return True
    empresa_linha = _normalizar_texto(cells[4])
    empresa_dados = _normalizar_texto(dados.company_name)
    if not empresa_dados:
        return True

    base = empresa_dados.split("(", 1)[0].strip()
    if base and base not in empresa_linha:
        return False

    # Para grupos com varias filiais de mesmo nome (ex.: LCR), o nome base nao
    # basta. Exige tambem o sufixo da filial quando ele existe no cadastro.
    sufixo = ""
    m = re.search(r"\((\d{4}-\d{2})\)", dados.company_name or "")
    if m:
        sufixo = m.group(1).lower()

    # Só exige o sufixo quando ele faz parte do nome cadastrado/mostrado pelo
    # Agilize. Empresas de CNPJ único (MM, WI, LEAO etc.) aparecem sem sufixo.
    if sufixo and sufixo not in empresa_linha:
        return False
    return True


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


def _intervalo_historico_nfse(emissao_iso: str, meses_anteriores: int = 3) -> tuple[str, str]:
    """Janela de historico da NFS-e usando meses completos anteriores.

    A busca antiga consultava somente o mes imediatamente anterior. Isso falhava
    quando o modelo valido estava dois meses antes (ex.: nota atual em setembro e
    referencia FINNET em julho). A janela padrao agora cobre o mes anterior + dois
    meses extras, sem incluir o mes da nota atual.
    """
    if emissao_iso:
        base = datetime.strptime(emissao_iso, "%Y-%m-%d")
    else:
        base = datetime.now()

    meses_anteriores = max(1, int(meses_anteriores or 3))

    # Primeiro dia do mes mais antigo da janela.
    total_inicio = base.year * 12 + (base.month - 1) - meses_anteriores
    inicio_ano = total_inicio // 12
    inicio_mes = total_inicio % 12 + 1

    # Ultimo dia do mes imediatamente anterior ao da nota atual.
    if base.month == 1:
        fim_ano, fim_mes = base.year - 1, 12
    else:
        fim_ano, fim_mes = base.year, base.month - 1
    fim_dia = monthrange(fim_ano, fim_mes)[1]

    return (
        f"{inicio_ano:04d}-{inicio_mes:02d}-01",
        f"{fim_ano:04d}-{fim_mes:02d}-{fim_dia:02d}",
    )


def _esperar_lista(page, timeout=15000):
    page.locator("#searchInput").wait_for(state="visible", timeout=timeout)


def _esperar_modal(page, timeout=15000):
    # O Agilize atual abre o registro em duas etapas Livewire:
    # 1) openNfsModal(id) no componente da lista;
    # 2) evento openModal que monta modals.nfs.edit-nfs.
    # Esperar apenas #modal-container nao e suficiente porque o container pode existir
    # antes de o componente de edicao terminar de hidratar.
    page.locator("#modal-container").wait_for(state="visible", timeout=timeout)
    try:
        page.locator("#observacao").wait_for(state="visible", timeout=timeout)
    except Exception:
        # O fallback por wire:initial-data e tratado em _ler_dados_modal_edicao.
        pass


def _acao_editar_na_linha(row):
    """Localiza a acao de editar/ver nota nas versoes antiga e nova do Agilize."""
    tentativas = [
        ("link", "Editar"),
        ("button", "Editar"),
        ("button", "Ver nota"),
        ("link", "Ver nota"),
        ("button", "Enviar"),
        ("link", "Enviar"),
        ("button", "Enviar nota"),
        ("link", "Enviar nota"),
        ("button", "Completar"),
        ("link", "Completar"),
        ("button", "Abrir"),
        ("link", "Abrir"),
    ]
    for role, name in tentativas:
        try:
            loc = row.get_by_role(role, name=name)
            if loc.count() and loc.first.is_visible():
                return loc.first
        except Exception:
            pass

    # Agilize novo: <button wire:click="openNfsModal(16529)">Editar</button>
    # Agilize antigo: wire:click="$emit('openModal', 'modals.nfs.edit-nfs', [...])"
    for selector in (
        r'[wire\:click^="openNfsModal("]',
        r'[wire\:click*="modals.nfs.edit-nfs"]',
        r'[wire\:click*="import"][wire\:click*="nfs"]',
    ):
        try:
            loc = row.locator(selector)
            if loc.count() and loc.first.is_visible():
                return loc.first
        except Exception:
            pass

    # v0.9.8: o Agilize passou a exibir algumas acoes apenas como icone, sem
    # texto/aria-label. Como a linha ja foi validada pelo numero da nota, o
    # ultimo controle clicavel da coluna de acoes e um fallback seguro.
    for selector in (
        'td:last-child button',
        'td:last-child a',
        'td:last-child [role="button"]',
        r'td:last-child [wire\:click]',
        'button[title]',
        'a[title]',
    ):
        try:
            loc = row.locator(selector)
            for i in range(loc.count() - 1, -1, -1):
                item = loc.nth(i)
                if item.is_visible() and item.is_enabled():
                    return item
        except Exception:
            pass
    return None


def _abrir_modal_edicao(page, row, logger: Optional[Logger] = None, timeout: int = 15000) -> bool:
    acao = _acao_editar_na_linha(row)
    if acao is None:
        # Ultimo fallback: em algumas versoes a acao existe apenas como um
        # controle focavel/icone na ultima celula. Simula o mesmo fluxo manual
        # de TAB + ENTER, mas restrito a linha exata que ja foi validada.
        try:
            focaveis = row.locator('td:last-child button, td:last-child a, td:last-child [tabindex="0"], td:last-child [role="button"]')
            for i in range(focaveis.count() - 1, -1, -1):
                item = focaveis.nth(i)
                if not item.is_visible():
                    continue
                item.focus()
                page.keyboard.press("Enter")
                _esperar_modal(page, timeout=min(timeout, 8000))
                _log(logger, "Editar/Ver nota aberto pelo fallback de teclado da coluna de acoes.")
                return True
        except Exception:
            pass
        _log(logger, "Nota-base encontrada, mas o botao Editar/Ver nota nao foi localizado.")
        return False
    try:
        acao.click()
        _esperar_modal(page, timeout=timeout)
        return True
    except Exception as exc:
        _log(logger, f"Falha ao abrir Editar/Ver nota: {exc}")
        return False


def _parse_initial_livewire_edicao(raw: str) -> dict:
    """Extrai serverMemo.data.nfs quando o payload e do modal edit-nfs."""
    if not raw:
        return {}
    try:
        payload = json.loads(html.unescape(raw))
    except Exception:
        return {}
    nome = str(payload.get('fingerprint', {}).get('name', ''))
    if nome != 'modals.nfs.edit-nfs':
        return {}
    nfs = payload.get('serverMemo', {}).get('data', {}).get('nfs', {})
    return nfs if isinstance(nfs, dict) else {}


def _dados_initial_livewire_edicao(page) -> dict:
    """Le serverMemo.data.nfs do componente edit-nfs quando o atributo ainda existe."""
    try:
        componentes = page.locator(r'[wire\:initial-data]')
        candidatos = []
        for i in range(componentes.count()):
            componente = componentes.nth(i)
            raw = componente.get_attribute('wire:initial-data') or ''
            if not raw:
                continue
            nfs = _parse_initial_livewire_edicao(raw)
            if not nfs:
                continue
            try:
                visivel = componente.is_visible()
            except Exception:
                visivel = False
            candidatos.append((visivel, nfs))
        for visivel, nfs in candidatos:
            if visivel:
                return nfs
        return candidatos[-1][1] if candidatos else {}
    except Exception:
        return {}


def _dados_livewire_modal_visivel(page) -> dict:
    """Le o estado do componente Livewire que contem a Observacao visivel.

    O Livewire remove wire:initial-data depois da hidratacao em alguns ciclos. Nesse
    momento a fonte confiavel passa a ser o componente em window.Livewire. Tambem
    devolvemos o valor real do textarea como contingencia.
    """
    try:
        result = page.evaluate(
            """() => {
                const itens = Array.from(document.querySelectorAll('textarea#observacao, textarea[id*=\"observ\"]'));
                const visivel = itens.find((el) => {
                    const s = window.getComputedStyle(el);
                    const r = el.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
                });
                if (!visivel) return {};

                let root = visivel;
                while (root && !root.hasAttribute('wire:id')) root = root.parentElement;
                const wireId = root ? root.getAttribute('wire:id') : '';
                const out = {
                    description: '',
                    user_for_approval_id: null,
                    textarea_value: visivel.value || '',
                    textarea_text: visivel.textContent || '',
                    wire_id: wireId || '',
                    source: ''
                };

                let comp = null;
                try {
                    if (wireId && window.Livewire && typeof window.Livewire.find === 'function') {
                        comp = window.Livewire.find(wireId);
                    }
                } catch (_) {}

                const tentarGet = (obj, key) => {
                    if (!obj) return undefined;
                    try { if (typeof obj.get === 'function') return obj.get(key); } catch (_) {}
                    try { if (obj.$wire && typeof obj.$wire.get === 'function') return obj.$wire.get(key); } catch (_) {}
                    return undefined;
                };

                let desc = tentarGet(comp, 'nfs.description');
                let approval = tentarGet(comp, 'nfs.user_for_approval_id');

                try {
                    const nfs = comp && comp.serverMemo && comp.serverMemo.data && comp.serverMemo.data.nfs;
                    if ((desc === undefined || desc === null || desc === '') && nfs) desc = nfs.description;
                    if ((approval === undefined || approval === null || approval === '') && nfs) approval = nfs.user_for_approval_id;
                } catch (_) {}
                try {
                    const nfs = comp && comp.data && comp.data.nfs;
                    if ((desc === undefined || desc === null || desc === '') && nfs) desc = nfs.description;
                    if ((approval === undefined || approval === null || approval === '') && nfs) approval = nfs.user_for_approval_id;
                } catch (_) {}

                if (desc !== undefined && desc !== null && String(desc).trim()) {
                    out.description = String(desc);
                    out.source = 'livewire-runtime';
                } else if ((visivel.value || '').trim()) {
                    out.description = visivel.value;
                    out.source = 'textarea-value';
                } else if ((visivel.textContent || '').trim()) {
                    out.description = visivel.textContent;
                    out.source = 'textarea-text';
                }
                if (approval !== undefined && approval !== null && approval !== '') {
                    out.user_for_approval_id = approval;
                }
                return out;
            }"""
        )
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _ler_dados_modal_edicao(page, logger: Optional[Logger] = None) -> tuple[str, str]:
    """Retorna (observacao, aprovador) do modal de edicao realmente visivel.

    Prioridade:
    1. estado runtime do componente Livewire ativo;
    2. wire:initial-data enquanto ainda existir;
    3. valor/texto do textarea visivel.
    """
    runtime = _dados_livewire_modal_visivel(page)
    obs = str(runtime.get('description') or '')
    aprovador_id = runtime.get('user_for_approval_id')
    fonte = str(runtime.get('source') or '')

    if not obs:
        dados_livewire = _dados_initial_livewire_edicao(page)
        obs = str(dados_livewire.get('description') or '')
        if aprovador_id in (None, ''):
            aprovador_id = dados_livewire.get('user_for_approval_id')
        if obs:
            fonte = 'wire-initial-data'

    if not obs:
        loc = _primeiro_visivel(
            page,
            [
                '#observacao',
                "textarea[id*='observ']",
                r"textarea[wire\:model*='description']",
                r"textarea[wire\:model*='observ']",
            ],
        )
        if loc is not None:
            try:
                obs = loc.input_value() or ''
                fonte = 'textarea-visible' if obs else fonte
            except Exception:
                pass

    aprovador = ''
    if aprovador_id not in (None, ''):
        try:
            opts = page.locator(f'#user_for_approval option[value="{aprovador_id}"]')
            for i in range(opts.count()):
                opt = opts.nth(i)
                if opt.is_visible():
                    aprovador = opt.inner_text().strip()
                    break
            if not aprovador and opts.count():
                aprovador = opts.last.inner_text().strip()
        except Exception:
            pass

    if not aprovador:
        loc = _primeiro_visivel(
            page,
            [
                '#user_for_approval',
                "select[id*='approval']",
                r"select[wire\:model*='approval']",
                r"select[wire\:model*='aprov']",
            ],
        )
        if loc is not None:
            try:
                aprovador = loc.locator('option:checked').inner_text().strip()
                if aprovador.lower().startswith(("escolha", "selecione")):
                    aprovador = ''
            except Exception:
                pass

    if obs:
        _log(logger, f"Observacao lida da nota-base ({fonte or 'modal'}), {len(obs)} caractere(s).")
    else:
        _log(logger, "Modal correto foi aberto, mas nenhuma fonte de Observacao retornou texto.")
    return obs, aprovador


def _aguardar_livewire(page, minimo_ms: int = 250, timeout: int = 5000):
    """Espera a atualizacao Livewire terminar sem impor atrasos longos em formularios."""
    page.wait_for_timeout(minimo_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        pass


def _aguardar_pesquisa_livewire(
    page,
    minimo_ms: int = 1750,
    timeout: int = 7500,
    assentamento_ms: int = 450,
):
    """Espera um pouco mais nas pesquisas antes de ler a grade.

    O Agilize atual atualiza filtros/listas em etapas. Em maquinas ou conexoes mais
    lentas, o debounce podia terminar e a automacao ler o ``tbody`` antes da nova
    grade aparecer visualmente. Alem do tempo minimo, aguardamos o texto da tabela
    estabilizar por duas leituras e damos um pequeno tempo final de renderizacao.

    O atraso extra e aplicado somente a pesquisas/listagens; o preenchimento dos
    campos do formulario continua usando ``_aguardar_livewire`` para nao deixar o
    processo inteiro artificialmente lento.
    """
    _aguardar_livewire(page, minimo_ms=minimo_ms, timeout=timeout)

    deadline = time.monotonic() + 2.5
    ultimo = None
    leituras_estaveis = 0
    while time.monotonic() < deadline:
        try:
            tbody = page.locator("tbody")
            atual = tbody.inner_text(timeout=500) if tbody.count() else ""
        except Exception:
            atual = ""

        if atual == ultimo:
            leituras_estaveis += 1
            if leituras_estaveis >= 2:
                break
        else:
            ultimo = atual
            leituras_estaveis = 0
        page.wait_for_timeout(250)

    page.wait_for_timeout(assentamento_ms)


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
    """Retorna o primeiro elemento realmente visivel, inclusive quando ha IDs duplicados em modais ocultos."""
    for selector in selectors:
        try:
            loc = page.locator(selector)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible():
                    return item
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

    inicio, fim = _intervalo_historico_nfse(dados.emissao)
    _log(
        logger,
        f"Buscando observacao completa e aprovador nas NFS-e efetuadas entre {inicio} e {fim} (3 meses anteriores)...",
    )

    _esperar_lista(page)

    # Ajusta empresa/tipo/status primeiro. O Livewire pode reconstruir os campos
    # de data ao trocar esses filtros; por isso as datas ficam por ultimo.
    page.locator("#underline_select").select_option(str(dados.company_id))
    page.locator("#searchType").select_option(label="Documento fornecedor")
    _selecionar_status_efetuada(page, logger)

    date_start = page.locator(r'input[wire\:model\.debounce\.1000ms="filter.dateStart"]')
    date_end = page.locator(r'input[wire\:model\.debounce\.1000ms="filter.dateEnd"]')
    date_start.fill(inicio)
    date_end.fill(fim)
    _aguardar_livewire(page, minimo_ms=1550, timeout=7000)

    # Confere se o rerender preservou o intervalo e reaplica uma vez se preciso.
    try:
        atual_inicio = date_start.input_value().strip()
        atual_fim = date_end.input_value().strip()
        if atual_inicio != inicio or atual_fim != fim:
            date_start.fill(inicio)
            date_end.fill(fim)
            _aguardar_livewire(page, minimo_ms=1550, timeout=7000)
            atual_inicio = date_start.input_value().strip()
            atual_fim = date_end.input_value().strip()
        _log(logger, f"Notas NFS-E: datas confirmadas na tela = {atual_inicio} ate {atual_fim}.")
    except Exception as exc:
        _log(logger, f"Notas NFS-E: nao foi possivel confirmar visualmente os filtros de data: {exc}")

    page.locator("#searchInput").fill(dados.provider_cnpj)
    _aguardar_pesquisa_livewire(page, minimo_ms=1800, timeout=7500)

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
        if not _linha_mesma_empresa(cells, dados):
            _log(logger, f"Ignorando historico de outra empresa: {empresa_txt}")
            continue
        if not _linha_nfs_efetuada(cells):
            situacao_txt = cells[8] if len(cells) > 8 else "nao identificada"
            _log(logger, f"Ignorando nota {cells[1]}: Situacao de Entrada = {situacao_txt}; esperado Efetuada.")
            continue
        try:
            emissao_dt = datetime.strptime(emissao_txt, "%d/%m/%Y")
        except Exception:
            emissao_dt = datetime.min
        candidatos.append((emissao_dt, i, cells[1], emissao_txt, empresa_txt))

    if not candidatos:
        _log(logger, f"Nenhuma nota-base EFETUADA encontrada para esta empresa e fornecedor entre {inicio} e {fim}.")
        return "", "", ""

    candidatos.sort(reverse=True, key=lambda x: x[0])
    _, row_index, numero, emissao_txt, empresa_txt = candidatos[0]
    _log(logger, f"Nota-base encontrada: {numero} - {emissao_txt} - {empresa_txt}")

    rows = page.locator("tbody tr")
    row = rows.nth(row_index)
    if not _abrir_modal_edicao(page, row, logger):
        return "", "", f"{numero} - {emissao_txt}"

    obs, aprovador = _ler_dados_modal_edicao(page, logger)

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
    """Preenche o CNPJ e espera o Livewire concluir a busca do fornecedor."""
    campo = _primeiro_visivel(page, ["#fornecedor", r"input[wire\:model*='provider_cnpj']"])
    if campo is None:
        raise RuntimeError("Campo CNPJ do fornecedor nao localizado no formulario visivel.")

    campo.click()
    campo.press("Control+A")
    campo.press_sequentially(cnpj, delay=20)
    _esperar_debounce_fornecedor(page)

    def valor_atual():
        try:
            loc = _primeiro_visivel(page, ["#fornecedor", r"input[wire\:model*='provider_cnpj']"])
            return loc.input_value() if loc is not None else ""
        except Exception:
            return ""

    if _digits(valor_atual()) != _digits(cnpj):
        campo = _primeiro_visivel(page, ["#fornecedor", r"input[wire\:model*='provider_cnpj']"])
        if campo is None:
            raise RuntimeError("Campo CNPJ do fornecedor desapareceu apos atualizacao do Livewire.")
        campo.evaluate(
            """(el, value) => {
                el.focus();
                el.value = value;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
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

    try:
        page.wait_for_function(
            """() => Array.from(document.querySelectorAll('#nome_fornecedor')).some((el) => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (el.value || '').trim().length > 0;
            })""",
            timeout=4500,
        )
    except PlaywrightTimeoutError:
        pass

    nome = _primeiro_visivel(page, ["#nome_fornecedor", r"input[wire\:model*='provider_name']"])
    try:
        nome_atual = nome.input_value().strip() if nome is not None else ""
    except Exception:
        nome_atual = ""

    if nome_atual:
        _log(logger, f"Nome do fornecedor retornado pelo Agilize: {nome_atual}")
    elif provider_name and nome is not None:
        nome.fill(provider_name)
        _aguardar_livewire(page, minimo_ms=180, timeout=3000)
        _log(logger, "Nome do fornecedor nao retornou pelo CNPJ; usado nome do PDF como contingencia.")


def _preencher_campos_complementares(page, dados: NotaDados, anexos_pdf: list[str], logger: Optional[Logger], contexto: str, anexo_obrigatorio: bool = True):
    """Preenche os campos editaveis comuns ao modal novo e ao modal importado."""
    if dados.aprovador:
        try:
            select = _primeiro_visivel(page, ["#user_for_approval", r"select[wire\:model*='user_for_approval_id']"])
            if select is not None:
                option = select.locator("option", has_text=dados.aprovador)
                if option.count() == 0:
                    _aguardar_livewire(page, minimo_ms=200, timeout=3500)
                select.select_option(label=dados.aprovador)
                _aguardar_livewire(page, minimo_ms=180, timeout=3000)
        except Exception:
            _log(logger, f"Aprovador '{dados.aprovador}' nao estava disponivel para esta empresa.")

    if dados.observacao:
        observacao = _primeiro_visivel(
            page,
            ["#observacao", r"textarea[wire\:model='nfs.description']", r"textarea[wire\:model*='description']"],
        )
        if observacao is None:
            raise RuntimeError(f"Campo Observacao nao localizado no {contexto}.")

        observacao.fill(dados.observacao)
        _aguardar_livewire(page, minimo_ms=320, timeout=4500)

        observacao = _primeiro_visivel(page, ["#observacao", r"textarea[wire\:model*='description']"])
        valor_obs = observacao.input_value() if observacao is not None else ""
        if valor_obs.strip() != dados.observacao.strip():
            if observacao is None:
                raise RuntimeError("Campo Observacao desapareceu apos sincronizacao do Livewire.")
            observacao.evaluate(
                """(el, value) => {
                    el.focus();
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.blur();
                }""",
                dados.observacao,
            )
            _aguardar_livewire(page, minimo_ms=350, timeout=4500)

        observacao = _primeiro_visivel(page, ["#observacao", r"textarea[wire\:model*='description']"])
        valor_final = observacao.input_value() if observacao is not None else ""
        if not valor_final.strip():
            raise RuntimeError(
                "O Agilize apagou a Observacao durante a sincronizacao; "
                "preenchimento interrompido para evitar um lancamento incompleto."
            )
        _log(logger, f"Observacao confirmada no {contexto}: {len(valor_final)} caractere(s).")

    if dados.vencimento:
        venc = _primeiro_visivel(
            page,
            [
                '#due_date\\.0',
                r"input[wire\:model*='due_date']",
                r"input[wire\:model*='dueDate']",
                '#modal-container input[type="date"]',
            ],
        )
        if venc is not None:
            venc.fill(dados.vencimento)
            _aguardar_livewire(page, minimo_ms=180, timeout=3000)
            _log(logger, f"Vencimento preenchido no {contexto}: {dados.vencimento}.")

    anexos = [str(Path(p).resolve()) for p in anexos_pdf if p]
    if not anexos:
        raise RuntimeError("Nenhum PDF foi informado para o campo Anexo do Agilize.")
    arquivo = _primeiro_visivel(page, ["#file_input", 'input[type="file"]'])
    anexou = False
    if arquivo is None:
        if anexo_obrigatorio:
            raise RuntimeError(f"Campo Anexo nao localizado no {contexto}.")
        _log(
            logger,
            f"Campo Anexo nao esta disponivel no {contexto}; o registro existente sera mantido sem tentar reenviar anexos.",
        )
    else:
        arquivo.set_input_files(anexos)
        anexou = True
        _log(logger, f"{len(anexos)} PDF(s) adicionados ao campo Anexo do Agilize.")

    if dados.observacao and anexou:
        _aguardar_livewire(page, minimo_ms=180, timeout=3000)
        observacao = _primeiro_visivel(page, ["#observacao", r"textarea[wire\:model*='description']"])
        valor_final = observacao.input_value() if observacao is not None else ""
        if not valor_final.strip():
            raise RuntimeError("A Observacao foi perdida apos anexar os PDFs; lancamento nao foi liberado para conferencia.")
        _log(logger, "Observacao permaneceu preenchida apos anexar os PDFs.")


def _preencher_create(page, dados: NotaDados, anexos_pdf: list[str], logger: Optional[Logger]):
    _log(logger, "Nenhuma importacao pendente correspondente foi encontrada. Abrindo formulario Enviar Nota...")
    page.get_by_role("button", name="Enviar Nota").click()
    _esperar_modal(page)

    empresa = _primeiro_visivel(page, ["#empresa", r"select[wire\:model*='company_id']"])
    if empresa is not None and (dados.company_id or dados.company_cnpj or dados.company_name):
        if not _selecionar_empresa_por_dados(
            page,
            dados,
            ["#empresa", r"select[wire\:model*='company_id']"],
            logger,
            "novo lancamento",
        ) and dados.company_id:
            raise RuntimeError("Nao foi possivel selecionar a Empresa no formulario visivel.")

    if dados.provider_cnpj:
        _preencher_cnpj(page, dados.provider_cnpj, dados.provider_name, logger)

    if dados.numero:
        numero = _primeiro_visivel(page, ["#numero", r"input[wire\:model*='number']"])
        if numero is not None:
            numero.fill(str(dados.numero))
    if dados.valor:
        valor = _primeiro_visivel(page, ["#valor", r"input[wire\:model*='value']"])
        if valor is not None:
            valor.fill(dados.valor)
    if dados.emissao:
        issued = _primeiro_visivel(page, ["#issued", r"input[wire\:model*='issued_at']"])
        if issued is not None:
            issued.fill(dados.emissao)

    _preencher_campos_complementares(page, dados, anexos_pdf, logger, "novo lancamento")
    _log(logger, "Formulario preenchido. O envio final continua manual.")


def _periodo_mes_da_nota(emissao_iso: str) -> tuple[str, str]:
    try:
        base = datetime.strptime(emissao_iso, "%Y-%m-%d")
    except Exception:
        base = datetime.now()
    ultimo = monthrange(base.year, base.month)[1]
    return f"{base.year:04d}-{base.month:02d}-01", f"{base.year:04d}-{base.month:02d}-{ultimo:02d}"


def _selecionar_todas_empresas(page, logger: Optional[Logger] = None) -> bool:
    """Remove o filtro de empresa na ultima tentativa de localizar a nota atual."""
    alvo = _primeiro_visivel(page, ["#underline_select", r"select[wire\:model*='company']"])
    if alvo is None:
        return False
    try:
        options = alvo.locator("option")
        for i in range(options.count()):
            opt = options.nth(i)
            texto = _normalizar_texto(opt.inner_text())
            valor = (opt.get_attribute("value") or "").strip()
            if "todas" in texto or "todas as empresas" in texto:
                alvo.select_option(valor)
                _aguardar_livewire(page, minimo_ms=220, timeout=4000)
                _log(logger, "Ultima tentativa de duplicidade: pesquisa em todas as empresas.")
                return True
        for valor in ("0", ""):
            try:
                alvo.select_option(valor)
                _aguardar_livewire(page, minimo_ms=220, timeout=4000)
                _log(logger, "Ultima tentativa de duplicidade: filtro de empresa removido.")
                return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def _periodo_busca_ampla(emissao_iso: str) -> tuple[str, str]:
    """Janela ampla para a ultima tentativa de encontrar um numero ja existente."""
    try:
        base = datetime.strptime(emissao_iso, "%Y-%m-%d")
    except Exception:
        base = datetime.now()
    return f"{base.year - 1:04d}-01-01", f"{base.year + 1:04d}-12-31"


def _periodo_busca_importada_por_fornecedor(emissao_iso: str, meses_anteriores: int = 3) -> tuple[str, str]:
    """Periodo do fallback da nota atual: meses anteriores + mes da emissao.

    Diferente do historico usado para copiar observacao, esta busca PRECISA
    incluir o mes atual, pois procura o proprio pre-cadastro importado da nota.
    """
    try:
        base = datetime.strptime(emissao_iso, "%Y-%m-%d")
    except Exception:
        base = datetime.now()

    meses_anteriores = max(2, int(meses_anteriores or 3))
    total_inicio = base.year * 12 + (base.month - 1) - meses_anteriores
    inicio_ano = total_inicio // 12
    inicio_mes = total_inicio % 12 + 1
    fim_dia = monthrange(base.year, base.month)[1]
    return (
        f"{inicio_ano:04d}-{inicio_mes:02d}-01",
        f"{base.year:04d}-{base.month:02d}-{fim_dia:02d}",
    )


def _selecionar_tipo_pesquisa(page, termos: tuple[str, ...]) -> bool:
    try:
        select = page.locator("#searchType")
        if not select.count() or not select.first.is_visible():
            return False
        options = select.first.locator("option")
        termos_norm = tuple(_normalizar_texto(t) for t in termos if t)
        # Rotulos exatos primeiro. "Fornecedor" nao pode selecionar
        # "Documento fornecedor" ao pesquisar uma razao social.
        for exato in (True, False):
            for termo in termos_norm:
                for i in range(options.count()):
                    opt = options.nth(i)
                    texto = _normalizar_texto(opt.inner_text())
                    if termo in ("fornecedor", "nome") and any(t in texto for t in ("documento", "cnpj")):
                        continue
                    corresponde = (texto == termo) if exato else (termo in texto)
                    if corresponde:
                        select.first.select_option(opt.get_attribute("value") or "")
                        _aguardar_livewire(page, minimo_ms=350, timeout=4000)
                        return True
    except Exception:
        return False
    return False


def _coletar_linhas_importada_prefixada(page, dados: NotaDados):
    candidatos = []
    rows = page.locator("tbody tr")
    for i in range(rows.count()):
        try:
            cells = [x.strip() for x in rows.nth(i).locator("th, td").all_inner_texts()]
        except Exception:
            continue
        ok, motivo = _linha_importada_prefixada_corresponde(cells, dados)
        if ok:
            candidatos.append((i, cells))
    return candidatos


def _localizar_importada_prefixada_por_fornecedor(page, dados: NotaDados, logger: Optional[Logger], estrito: bool = False):
    """Fallback anti-duplicidade para numero importado incorretamente pelo Agilize.

    Pesquisa o fornecedor em NFS-E com um periodo que inclui o mes atual e so
    aceita uma linha quando o numero cadastrado termina no numero fiscal esperado
    E empresa/CNPJ/valor/emissao conferem.
    """
    if not dados.numero or (not dados.provider_cnpj and not dados.provider_name):
        return None

    _log(
        logger,
        f"Nota {dados.numero} nao foi localizada pelo numero exato. "
        "Tentando localizar pre-cadastro do fornecedor com possivel prefixo indevido no numero...",
    )
    _garantir_lista_nfs(page)
    if not _selecionar_status_todos(page, logger):
        raise RuntimeError("Todos os status nao puderam ser selecionados em NFS-E. Por seguranca, nenhum novo lancamento foi criado.")
    _selecionar_empresa_por_dados(
        page, dados, ["#underline_select", r"select[wire\:model*='company']"],
        logger, "fallback por fornecedor da nota atual",
    )

    inicio, fim = _periodo_busca_importada_por_fornecedor(dados.emissao)
    tentativas: list[tuple[str, tuple[str, ...], str]] = []
    if dados.provider_cnpj:
        tentativas.append(("CNPJ", ("Documento fornecedor", "CNPJ", "Documento"), dados.provider_cnpj))
    if dados.provider_name:
        tentativas.append(("NOME", ("Nome fornecedor", "Fornecedor", "Pesquisar tudo", "Tudo"), dados.provider_name.strip()))

    pesquisas_concluidas = 0
    for rotulo, tipos, valor_busca in tentativas:
        if not valor_busca:
            continue
        selecionou = _selecionar_tipo_pesquisa(page, tipos)
        if not selecionou:
            _log(logger, f"Notas NFS-E: tipo de pesquisa por {rotulo} indisponivel; tentando a proxima opcao.")
            continue

        # A pesquisa tambem pode restaurar o periodo. Preenche o termo antes
        # das datas e so consulta as linhas apos confirmar ambos na tela.
        _pesquisar_lista_com_periodo(page, valor_busca, inicio, fim, logger)
        pesquisas_concluidas += 1
        _log(logger, f"Notas NFS-E: pesquisa por {rotulo} = '{valor_busca}', periodo confirmado {inicio} ate {fim}.")
        candidatos = _coletar_linhas_importada_prefixada(page, dados)
        if estrito:
            candidatos = [(idx, cells) for idx, cells in candidatos if _linha_atual_confirmada(cells, dados)]
        if not candidatos:
            continue
        if len(candidatos) > 1:
            raise RuntimeError(
                f"Mais de um pre-cadastro compativel com a nota {dados.numero} foi encontrado em NFS-E. "
                "Confira os registros manualmente. Por seguranca, nenhum novo lancamento foi criado."
            )

        idx, cells = candidatos[0]
        numero_cadastrado = cells[1] if len(cells) > 1 else ""
        situacao = cells[8] if len(cells) > 8 else ""
        _log(
            logger,
            f"Registro atual localizado pelo fornecedor ({rotulo}) entre {inicio} e {fim}: "
            f"numero cadastrado {numero_cadastrado} termina com {dados.numero}; "
            "empresa, fornecedor, valor e emissao conferem.",
        )
        return {
            "score": 190,
            "idx": idx,
            "cells": cells,
            "motivos": [f"numero cadastrado com prefixo indevido: {numero_cadastrado}"],
            "situacao": situacao,
            "numero_cadastrado": numero_cadastrado,
            "match_prefixado": True,
        }

    if not pesquisas_concluidas:
        raise RuntimeError(
            "Nao foi possivel concluir a pesquisa por fornecedor em Notas NFS-E. "
            "Por seguranca, nenhum novo lancamento foi criado."
        )

    _log(
        logger,
        f"Fallback por fornecedor nao encontrou pre-cadastro compativel da nota {dados.numero} entre {inicio} e {fim}.",
    )
    return None


def _campos_periodo_lista(page):
    """Resolve novamente os locators a cada tentativa, pois a tela e reativa."""
    campo_ini = _primeiro_visivel(page, [
        r'input[wire\:model\.debounce\.1000ms="filter.dateStart"]',
        r'input[wire\:model*="dateStart"]', r'input[wire\:model*="startDate"]',
    ])
    campo_fim = _primeiro_visivel(page, [
        r'input[wire\:model\.debounce\.1000ms="filter.dateEnd"]',
        r'input[wire\:model*="dateEnd"]', r'input[wire\:model*="endDate"]',
    ])
    # Mesmo fallback ja utilizado pela pesquisa historica, sem supor novos IDs.
    dates = page.locator('input[type="date"]:visible')
    if dates.count() >= 2:
        if campo_ini is None:
            campo_ini = dates.nth(0)
        if campo_fim is None:
            campo_fim = dates.nth(1)
    if campo_ini is None or campo_fim is None:
        raise RuntimeError("Os dois campos de data da lista nao foram localizados.")
    return campo_ini, campo_fim


def _aplicar_periodo_lista(page, inicio: str, fim: str, logger: Optional[Logger] = None, contexto: str = "Notas NFS-E") -> None:
    """Preenche, espera o debounce e confirma o intervalo efetivo; nunca falha em silencio."""
    if datetime.strptime(inicio, "%Y-%m-%d") > datetime.strptime(fim, "%Y-%m-%d"):
        raise ValueError("Data inicial maior que a data final da pesquisa.")
    ultimo_erro = ""
    for tentativa in range(1, 4):
        try:
            campo_ini, campo_fim = _campos_periodo_lista(page)
            if campo_ini.input_value().strip() != inicio:
                campo_ini.fill(inicio)
                campo_ini.press("Tab")
            # O preenchimento do inicio pode reconstruir o outro campo.
            _, campo_fim = _campos_periodo_lista(page)
            if campo_fim.input_value().strip() != fim:
                campo_fim.fill(fim)
                campo_fim.press("Tab")
            _aguardar_pesquisa_livewire(page, minimo_ms=1800, timeout=7500)
            campo_ini, campo_fim = _campos_periodo_lista(page)
            atual_inicio = campo_ini.input_value().strip()
            atual_fim = campo_fim.input_value().strip()
            if atual_inicio == inicio and atual_fim == fim:
                _log(logger, f"{contexto}: datas confirmadas na tela = {atual_inicio} ate {atual_fim}.")
                return
            ultimo_erro = f"a tela manteve {atual_inicio} ate {atual_fim}"
        except Exception as exc:
            ultimo_erro = str(exc)
        _log(logger, f"{contexto}: periodo nao confirmado ({tentativa}/3); reaplicando {inicio} ate {fim}.")
    raise RuntimeError(
        f"{contexto}: nao foi possivel confirmar o periodo {inicio} ate {fim}: {ultimo_erro}. "
        "Pesquisa inconclusiva. Por seguranca, nenhum novo lancamento foi criado."
    )


def _pesquisar_lista_com_periodo(page, valor: str, inicio: str, fim: str, logger: Optional[Logger] = None, contexto: str = "Notas NFS-E") -> None:
    """Texto e datas devem pertencer a mesma consulta, apos as reconstrucoes da tela."""
    for _ in range(2):
        page.locator("#searchInput").fill(str(valor))
        _aguardar_livewire(page, minimo_ms=1550, timeout=7000)
        _aplicar_periodo_lista(page, inicio, fim, logger, contexto)
        if page.locator("#searchInput").input_value().strip() == str(valor).strip():
            return
    raise RuntimeError(
        f"{contexto}: o texto de pesquisa nao permaneceu preenchido. "
        "Por seguranca, nenhum novo lancamento foi criado."
    )


def _coletar_linhas_mesmo_numero(page, dados: NotaDados, estrito: bool = False) -> list[tuple[int, int, list[str], list[str]]]:
    candidatos: list[tuple[int, int, list[str], list[str]]] = []
    rows = page.locator("tbody tr")
    for i in range(rows.count()):
        row = rows.nth(i)
        try:
            cells = [x.strip() for x in row.locator("th, td").all_inner_texts()]
        except Exception:
            continue
        if estrito and not _linha_atual_confirmada(cells, dados):
            continue
        score, motivos = _score_linha_mesmo_numero(cells, dados)
        if score >= 0:
            candidatos.append((score, i, cells, motivos))
    return candidatos


def _localizar_registro_existente(page, dados: NotaDados, logger: Optional[Logger], log_header: bool = True, estrito: bool = False):
    """Pesquisa exaustivamente o mesmo numero sem abrir o modal.

    Retorna o melhor candidato ou None. A busca continua usando todos os status,
    periodo amplo e todas as empresas antes de permitir a criacao de uma nota.
    """
    if not dados.numero:
        return None

    _garantir_lista_nfs(page)
    if log_header:
        _log(logger, f"Verificando se a nota {dados.numero} ja possui qualquer registro no Agilize antes de criar um novo...")

    if not _selecionar_tipo_pesquisa(page, ("Numero", "Pesquisar tudo", "Tudo")):
        raise RuntimeError("Filtro de pesquisa da NFS-e nao localizado. Por seguranca, nenhum novo lancamento foi criado.")
    if not _selecionar_status_todos(page, logger):
        raise RuntimeError("Todos os status nao puderam ser selecionados em NFS-E. Por seguranca, nenhum novo lancamento foi criado.")

    _selecionar_empresa_por_dados(
        page, dados, ["#underline_select", r"select[wire\:model*='company']"],
        logger, "pesquisa do registro existente",
    )
    inicio, fim = _periodo_busca_importada_por_fornecedor(dados.emissao)
    _log(logger, f"Notas NFS-E: periodo inicial de verificacao = {inicio} ate {fim} (mes da nota + 3 meses anteriores).")
    _pesquisar_lista_com_periodo(page, str(dados.numero), inicio, fim, logger)
    candidatos = _coletar_linhas_mesmo_numero(page, dados, estrito=estrito)

    if not candidatos:
        inicio_amplo, fim_amplo = _periodo_busca_ampla(dados.emissao)
        _log(logger, f"Nota {dados.numero} nao apareceu no periodo inicial; ampliando o periodo para {inicio_amplo} ate {fim_amplo}.")
        _pesquisar_lista_com_periodo(page, str(dados.numero), inicio_amplo, fim_amplo, logger)
        candidatos = _coletar_linhas_mesmo_numero(page, dados, estrito=estrito)

    if not candidatos:
        _selecionar_todas_empresas(page, logger)
        inicio_amplo, fim_amplo = _periodo_busca_ampla(dados.emissao)
        _pesquisar_lista_com_periodo(page, str(dados.numero), inicio_amplo, fim_amplo, logger)
        candidatos = _coletar_linhas_mesmo_numero(page, dados, estrito=estrito)

    if not candidatos:
        prefixado = _localizar_importada_prefixada_por_fornecedor(page, dados, logger, estrito=estrito)
        if prefixado:
            prefixado["estrito"] = estrito
            return prefixado

        _log(
            logger,
            f"Nenhum registro com o numero {dados.numero} foi encontrado apos pesquisar todos os status, periodo amplo e todas as empresas, "
            "nem pelo fallback seguro de fornecedor/prefixo. Somente agora sera permitido criar uma nova NFS-e.",
        )
        return None

    if estrito and len(candidatos) > 1:
        raise RuntimeError("Mais de uma NFS-e compativel foi encontrada. Por seguranca, nenhum novo lancamento foi criado.")
    candidatos.sort(key=lambda item: item[0], reverse=True)
    score, idx, cells, motivos = candidatos[0]
    situacao = cells[8] if len(cells) > 8 else ""
    if len(candidatos) > 1:
        _log(
            logger,
            f"Foram encontrados {len(candidatos)} registros com o numero {dados.numero}; "
            f"o melhor candidato foi selecionado por empresa/fornecedor/valor/emissao (score {score}).",
        )
    if motivos:
        _log(
            logger,
            "O registro existente possui divergencias secundarias, mas o numero da nota ja existe e sera reutilizado: "
            + "; ".join(motivos) + ".",
        )
    return {"score": score, "idx": idx, "cells": cells, "motivos": motivos, "situacao": situacao, "estrito": estrito}


def _buscar_e_abrir_importada_atual(page, dados: NotaDados, logger: Optional[Logger], precheck=...):
    """Localiza o registro atual e, quando necessario, abre-o para complemento."""
    if precheck is ...:
        registro = _localizar_registro_existente(page, dados, logger)
    else:
        registro = precheck

    if not registro:
        return {"existe": False, "aberto": False, "situacao": ""}

    situacao = str(registro.get("situacao") or "")
    numero_cadastrado = str(registro.get("numero_cadastrado") or "").strip()
    detalhe_numero = ""
    if numero_cadastrado and _normalizar_numero_nota(numero_cadastrado) != _normalizar_numero_nota(dados.numero):
        detalhe_numero = f" (pre-cadastrada como {numero_cadastrado})"
    _log(
        logger,
        f"Nota {dados.numero} ja possui registro no Agilize"
        + detalhe_numero
        + (f" (Situacao de Entrada = {situacao})" if situacao else "")
        + "; nenhuma duplicidade sera criada.",
    )

    if _status_ja_processado(situacao):
        _log(
            logger,
            f"Registro {dados.numero} ja esta em '{situacao}'. Ele ja foi enviado e nao precisa ser preparado novamente; seguindo para o proximo lancamento.",
        )
        return {"existe": True, "aberto": False, "ja_processado": True, "situacao": situacao}

    # Se o precheck veio de uma pesquisa anterior, a pagina pode ter sido usada
    # para consultar o historico. Refaz apenas a localizacao do registro atual.
    if precheck is not ...:
        registro = _localizar_registro_existente(page, dados, logger, log_header=False, estrito=bool(precheck.get("estrito")))
        if not registro:
            raise RuntimeError(
                f"A nota {dados.numero} foi localizada no pre-check, mas desapareceu ao reabrir a lista. "
                "Por seguranca, nenhum novo lancamento foi criado."
            )
        situacao = str(registro.get("situacao") or "")
        if _status_ja_processado(situacao):
            _log(logger, f"Registro passou para '{situacao}' durante a pesquisa; nao sera preenchido novamente.")
            return {"existe": True, "aberto": False, "ja_processado": True, "situacao": situacao}

    rows = page.locator("tbody tr")
    row = rows.nth(int(registro["idx"]))
    abriu = _abrir_modal_edicao(page, row, logger, timeout=12000)

    # Em 'Nao possui', a acao pode aparecer somente quando o filtro especifico
    # esta aplicado. Refiltra uma vez antes de considerar falha definitiva.
    if not abriu and _normalizar_texto(situacao) == "nao possui":
        _log(logger, "Acao da nota importada nao apareceu em Todos os status; repetindo a busca com Situacao = Nao possui.")
        _selecionar_status_nao_possui(page, logger)
        if registro.get("match_prefixado"):
            inicio, fim = _periodo_busca_importada_por_fornecedor(dados.emissao)
            numero_busca = str(registro.get("numero_cadastrado") or dados.numero)
            _selecionar_tipo_pesquisa(page, ("Numero", "Pesquisar tudo", "Tudo"))
            _pesquisar_lista_com_periodo(page, numero_busca, inicio, fim, logger)
            candidatos_prefixados = _coletar_linhas_importada_prefixada(page, dados)
            if candidatos_prefixados:
                idx, _cells = candidatos_prefixados[0]
                abriu = _abrir_modal_edicao(page, page.locator("tbody tr").nth(idx), logger, timeout=12000)
        else:
            inicio, fim = _periodo_busca_importada_por_fornecedor(dados.emissao)
            _selecionar_tipo_pesquisa(page, ("Numero", "Pesquisar tudo", "Tudo"))
            _pesquisar_lista_com_periodo(page, str(dados.numero), inicio, fim, logger)
            candidatos = _coletar_linhas_mesmo_numero(page, dados, estrito=bool(registro.get("estrito")))
            if candidatos:
                candidatos.sort(key=lambda item: item[0], reverse=True)
                _score, idx, _cells, _motivos = candidatos[0]
                abriu = _abrir_modal_edicao(page, page.locator("tbody tr").nth(idx), logger, timeout=12000)

    if not abriu:
        raise RuntimeError(
            f"A nota {dados.numero} ja existe no Agilize, mas a automacao nao conseguiu abrir Editar/Ver nota. "
            "Por seguranca, nenhum novo lancamento foi criado."
        )

    try:
        titulo = page.get_by_text("Enviar nota importada", exact=False)
        if titulo.count() and titulo.first.is_visible():
            _log(logger, "Modal 'Enviar nota importada (NFS-E)' aberto.")
        else:
            _log(logger, "Registro existente aberto em modo Editar/Ver nota.")
    except Exception:
        _log(logger, "Registro existente aberto em modo Editar/Ver nota.")
    return {"existe": True, "aberto": True, "ja_processado": False, "situacao": situacao}


def _preencher_destino(page, dados: NotaDados, anexos_pdf: list[str], logger: Optional[Logger], precheck=...):
    info = _buscar_e_abrir_importada_atual(page, dados, logger, precheck=precheck)
    if info.get("existe"):
        if info.get("ja_processado"):
            return "ja_processado"
        situacao = str(info.get("situacao") or "")
        anexo_obrigatorio = _normalizar_texto(situacao) == "nao possui"
        _preencher_campos_complementares(
            page,
            dados,
            anexos_pdf,
            logger,
            "lancamento importado",
            anexo_obrigatorio=anexo_obrigatorio,
        )
        _log(logger, "Registro existente complementado. O envio final continua manual.")
        return "importado"

    # A verificacao anterior ja foi exaustiva. Nao recarrega a pagina apenas para
    # abrir o formulario: isso elimina um reload completo por nota.
    _garantir_lista_nfs(page)
    page.get_by_role("button", name="Enviar Nota").wait_for(state="visible", timeout=12000)
    _preencher_create(page, dados, anexos_pdf, logger)
    return "novo"


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

        _preencher_destino(page, dados, anexos_pdf, logger)

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
