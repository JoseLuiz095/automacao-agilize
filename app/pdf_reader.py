from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF

from config import EMPRESAS, PAGADOR_EMPRESA_ALIASES
from models import NotaDados

CNPJ_RE = re.compile(r"(?<!\d)(\d{2}[.\s]?\d{3}[.\s]?\d{3}[\/\s]?\d{4}-?\d{2})(?!\d)")
DATE_RE = re.compile(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b")
MONEY_RE = re.compile(r"(?:R\$\s*)?((?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})")
NFSE_KEY_RE = re.compile(r"(?<!\d)(\d{44,60})(?!\d)")


@dataclass
class DocumentoClassificado:
    path: Path
    texto: str
    score_nota: int
    score_pagamento: int


def ler_pdf(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"O arquivo precisa ser PDF: {path.name}")

    doc = fitz.open(path)
    try:
        partes = [page.get_text("text") or "" for page in doc]
    finally:
        doc.close()

    texto = "\n".join(partes).strip()
    if len(re.sub(r"\s", "", texto)) < 20:
        raise ValueError(
            f"O PDF '{path.name}' nao possui texto suficiente para leitura automatica. "
            "Ele pode ser um PDF digitalizado/imagem."
        )
    return texto


def sem_acento(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value or "")
        if unicodedata.category(c) != "Mn"
    )


def normalizar_cnpj(value: str) -> str:
    nums = re.sub(r"\D", "", value or "")
    if len(nums) != 14:
        return (value or "").strip()
    return f"{nums[:2]}.{nums[2:5]}.{nums[5:8]}/{nums[8:12]}-{nums[12:]}"


def data_iso(data_value: str) -> str:
    value = (data_value or "").strip().replace("-", "/")
    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""


def data_br(data_value: str) -> str:
    """Converte uma data ISO (yyyy-mm-dd) para dd/mm/yyyy.

    Mantida aqui tambem por compatibilidade com modulos/versoes anteriores.
    """
    value = (data_value or "").strip()
    if not value:
        return ""
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return value


def _match_primeiro(texto: str, patterns: list[str], flags=re.IGNORECASE | re.MULTILINE) -> str:
    for pattern in patterns:
        m = re.search(pattern, texto, flags)
        if m:
            return m.group(1).strip()
    return ""


def _todos_cnpjs(texto: str) -> list[str]:
    encontrados: list[str] = []
    for raw in CNPJ_RE.findall(texto):
        cnpj = normalizar_cnpj(raw)
        if cnpj and cnpj not in encontrados:
            encontrados.append(cnpj)
    return encontrados


def _linhas(texto: str) -> list[str]:
    return [x.strip() for x in texto.splitlines() if x.strip()]


def _is_nota_debito(texto: str) -> bool:
    return "NOTA DE DEBITO" in sem_acento(texto).upper()


def _valor_vizinho_rotulo(texto: str, rotulos: tuple[str, ...], regex: re.Pattern, alcance: int = 4) -> str:
    linhas = _linhas(texto)
    rotulos_norm = tuple(sem_acento(x).upper() for x in rotulos)
    for i, linha in enumerate(linhas):
        norm = sem_acento(linha).upper().strip()
        if not any(rot in norm for rot in rotulos_norm):
            continue
        for delta in range(1, alcance + 1):
            for j in (i - delta, i + delta):
                if 0 <= j < len(linhas):
                    m = regex.search(linhas[j])
                    if m:
                        if regex is DATE_RE:
                            return m.group(0)
                        return m.group(1) if m.groups() else m.group(0)
    return ""


def _achar_fatura_nota_debito(texto: str) -> str:
    if not _is_nota_debito(texto):
        return ""
    inline = _match_primeiro(texto, [r"FATURA\s*[:\-]?\s*(\d{4,14})"])
    if inline:
        return inline.lstrip("0") or "0"
    value = _valor_vizinho_rotulo(texto, ("FATURA",), re.compile(r"(?<!\d)(\d{4,14})(?!\d)"), alcance=3)
    return value.lstrip("0") or ("0" if value else "")


def _achar_emissao_nota_debito(texto: str) -> str:
    if not _is_nota_debito(texto):
        return ""
    value = _valor_vizinho_rotulo(texto, ("EMISSAO",), DATE_RE, alcance=4)
    if value:
        return data_iso(value)
    datas = [m.group(0) for m in DATE_RE.finditer(texto)]
    if not datas:
        return ""
    parsed = []
    for raw in datas:
        try:
            parsed.append(datetime.strptime(raw, "%d/%m/%Y"))
        except ValueError:
            pass
    return max(parsed).strftime("%Y-%m-%d") if parsed else ""


def _achar_valor_nota_debito(texto: str) -> str:
    if not _is_nota_debito(texto):
        return ""
    value = _valor_vizinho_rotulo(texto, ("TOTAL",), MONEY_RE, alcance=4)
    if value:
        return value
    valores = MONEY_RE.findall(texto)
    return valores[-1] if valores else ""


def _achar_descricao_nota_debito(texto: str) -> str:
    if not _is_nota_debito(texto):
        return ""
    linhas = _linhas(texto)
    for i, linha in enumerate(linhas):
        if "CONTRATO" not in sem_acento(linha).upper():
            continue
        for cand in linhas[i + 1:i + 8]:
            norm = sem_acento(cand).upper()
            if MONEY_RE.fullmatch(cand) or re.fullmatch(r"[\d\W]+", cand):
                continue
            if len(cand) >= 12 and any(ch.isalpha() for ch in cand) and "TOTAL" not in norm:
                return cand[:1200]
    return ""


def _achar_nota_fiscal_referenciada_boleto(texto: str) -> str:
    """Retorna o numero da nota fiscal explicitamente referenciada no boleto/recibo.

    Alguns fornecedores (ex.: FINNET) imprimem no proprio boleto um resumo com:

        NOTA FISCAL
        47736
        FATURA
        23433

    O numero da nota e a chave mais forte para relacionar o boleto com o PDF fiscal.
    """
    upper = sem_acento(texto).upper()
    if not any(x in upper for x in ("RECIBO DO PAGADOR", "FICHA DE COMPENSACAO", "BOLETO")):
        return ""

    patterns = [
        r"NOTA\s+FISCAL\s*[:\-]?\s*\n\s*0*(\d{3,14})(?!\d)",
        r"NOTA\s+FISCAL\s*[:\-]?\s+0*(\d{3,14})(?!\d)",
    ]
    value = _match_primeiro(texto, patterns, re.IGNORECASE | re.MULTILINE)
    return value.lstrip("0") or ("0" if value else "")


def _achar_fatura_boleto(texto: str) -> str:
    """Extrai a fatura impressa no boleto como referencia secundaria."""
    upper = sem_acento(texto).upper()
    if not any(x in upper for x in ("RECIBO DO PAGADOR", "FICHA DE COMPENSACAO", "BOLETO")):
        return ""
    value = _match_primeiro(
        texto,
        [
            r"FATURA\s*[:\-]?\s*\n\s*0*(\d{3,14})(?!\d)",
            r"FATURA\s*[:\-]?\s+0*(\d{3,14})(?!\d)",
        ],
        re.IGNORECASE | re.MULTILINE,
    )
    return value.lstrip("0") or ("0" if value else "")


def _achar_fatura_generica(texto: str) -> str:
    value = _match_primeiro(
        texto,
        [
            r"FATURA\s*[:\-]?\s*0*(\d{3,14})(?!\d)",
            r"FATURA\s*[:\-]?\s*\n\s*0*(\d{3,14})(?!\d)",
        ],
    )
    return value.lstrip("0") or ("0" if value else "")


def _achar_numero_documento_boleto_por_frequencia(texto: str) -> str:
    from collections import Counter
    candidatos = []
    for linha in _linhas(texto):
        if re.fullmatch(r"\d{5,12}", linha):
            candidatos.append(linha)
    if not candidatos:
        return ""
    cont = Counter(candidatos)
    # Prioriza repeticao; em empate, numeros de 5-8 digitos sao tipicos de numero do documento.
    ordenados = sorted(
        cont.items(),
        key=lambda kv: (kv[1], 5 <= len(kv[0]) <= 8, -len(kv[0])),
        reverse=True,
    )
    return ordenados[0][0]


def _achar_vencimento_boleto(texto: str) -> str:
    upper = sem_acento(texto).upper()
    if "FICHA DE COMPENSACAO" not in upper and "RECIBO DO PAGADOR" not in upper:
        return ""
    datas = []
    for parts in DATE_RE.findall(texto):
        try:
            datas.append(datetime.strptime("/".join(parts), "%d/%m/%Y"))
        except ValueError:
            pass
    # Em boletos, o vencimento normalmente e a maior data impressa; datas de
    # documento/processamento ficam antes dele.
    return max(datas).strftime("%Y-%m-%d") if datas else ""


def _achar_empresa_por_pagador(texto: str):
    upper = sem_acento(texto).upper()
    for alias, cnpj in sorted(PAGADOR_EMPRESA_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in upper and cnpj in EMPRESAS:
            company_id, company_name = EMPRESAS[cnpj]
            return cnpj, company_id, company_name
    # Nomes unicos sem filial tambem podem ser resolvidos pelo proprio cadastro.
    matches = []
    for cnpj, (company_id, company_name) in EMPRESAS.items():
        base = sem_acento(company_name).upper().split("(")[0].strip()
        if base and base in upper:
            matches.append((cnpj, company_id, company_name))
    if len(matches) == 1:
        return matches[0]
    return "", None, ""


def _achar_referencia_documento(texto: str) -> str:
    return (
        _achar_numero_nota(texto)
        or _achar_nota_fiscal_referenciada_boleto(texto)
        or _achar_fatura_nota_debito(texto)
        or _achar_fatura_boleto(texto)
        or _achar_fatura_generica(texto)
        or _normalizar_documento_base(_achar_numero_documento_pagamento(texto))
    )


def _score_documento(texto: str) -> tuple[int, int]:
    upper = sem_acento(texto).upper()

    nota_keywords = {
        "DANFSE V2.0": 40,
        "DOCUMENTO AUXILIAR DA NFS-E": 35,
        "CHAVE DE ACESSO DA NFS-E": 25,
        "NUMERO DA NFS-E": 12,
        "PRESTADOR / FORNECEDOR": 10,
        "TOMADOR / ADQUIRENTE": 10,
        "SERVICO PRESTADO": 8,
        "COMPETENCIA DA NFS-E": 8,
        "VALOR TOTAL DA NFS-E": 8,
        "NFS-E": 4,
        "NOTA FISCAL ELETRONICA DE SERVICOS": 35,
        "NOTA FISCAL ELETRONICA DE SERVICO": 35,
        "NUMERO DA NOTA": 12,
        "PRESTADOR DE SERVICOS": 10,
        "TOMADOR DE SERVICOS": 10,
        "VALOR TOTAL DA NOTA": 8,
        "NOTA FISCAL": 4,
        "NOTA DE DEBITO": 22,
    }
    pagamento_keywords = {
        "FICHA DE COMPENSACAO": 40,
        "PAGAVEL EM QUALQUER BANCO": 30,
        "NOSSO NUMERO": 15,
        "VALOR DO DOCUMENTO": 12,
        "CEDENTE": 8,
        "SACADO": 8,
        "VENCIMENTO": 5,
        "BOLETO": 12,
        "PIX": 8,
    }

    nota = sum(peso for palavra, peso in nota_keywords.items() if palavra in upper)
    pagamento = sum(peso for palavra, peso in pagamento_keywords.items() if palavra in upper)

    if _achar_linha_digitavel(texto):
        pagamento += 35

    return nota, pagamento


def classificar_pdfs(paths: list[str | Path]) -> tuple[Path, Path]:
    """Retorna ``(nota_referencia, documento_pagamento)`` para 1 ou 2 PDFs.

    Com 2 PDFs, tenta separar a NFS-e oficial do recibo/boleto.
    Com 1 PDF, o mesmo arquivo e usado como fonte fiscal e de pagamento. Isso
    atende documentos combinados (recibo + boleto em um unico PDF). Se algum
    dado obrigatorio nao existir nesse arquivo, a validacao posterior informa
    exatamente o que faltou e o usuario pode adicionar o segundo documento.
    """
    unicos: list[Path] = []
    for item in paths:
        path = Path(item).resolve()
        if path.suffix.lower() == ".pdf" and path not in unicos:
            unicos.append(path)

    if len(unicos) not in (1, 2):
        raise ValueError("Adicione 1 ou 2 arquivos PDF.")

    if len(unicos) == 1:
        # O extrator ja possui fallbacks entre texto fiscal e texto de pagamento.
        # Reutilizar o mesmo PDF permite trabalhar com documentos combinados.
        ler_pdf(unicos[0])  # valida que o PDF possui texto utilizavel
        return unicos[0], unicos[0]

    docs: list[DocumentoClassificado] = []
    for path in unicos:
        texto = ler_pdf(path)
        score_nota, score_pagamento = _score_documento(texto)
        docs.append(DocumentoClassificado(path, texto, score_nota, score_pagamento))

    # O PDF oficial da NFS-e deve vencer mesmo quando o recibo/boleto tambem contem
    # uma representacao resumida da nota.
    nota = max(docs, key=lambda d: (d.score_nota - d.score_pagamento, d.score_nota))
    pagamento = docs[0] if docs[1].path == nota.path else docs[1]

    if nota.score_nota <= 0 and pagamento.score_pagamento <= 0:
        raise ValueError("Nao foi possivel reconhecer os documentos enviados.")

    # Alguns fornecedores entregam dois PDFs sem um DANFSe nacional claramente
    # identificavel. Nesses casos, mantemos o documento mais fiscal como referencia
    # e deixamos a validacao dos campos decidir se ha informacao suficiente.
    return nota.path, pagamento.path


def _achar_empresa_interna(texto: str):
    # Preferencia explicita pelo bloco TOMADOR/ADQUIRENTE do DANFSe.
    upper = sem_acento(texto).upper()
    pos = upper.find("TOMADOR / ADQUIRENTE")
    if pos >= 0:
        trecho = texto[pos:pos + 2200]
        for cnpj in _todos_cnpjs(trecho):
            if cnpj in EMPRESAS:
                company_id, company_name = EMPRESAS[cnpj]
                return cnpj, company_id, company_name

    for cnpj in _todos_cnpjs(texto):
        if cnpj in EMPRESAS:
            company_id, company_name = EMPRESAS[cnpj]
            return cnpj, company_id, company_name

    # Alguns boletos exibem somente o nome do pagador, sem o CNPJ do tomador.
    return _achar_empresa_por_pagador(texto)


def _achar_provider_cnpj(texto: str, company_cnpj: str) -> str:
    upper = sem_acento(texto).upper()

    for keyword in ("PRESTADOR / FORNECEDOR", "PRESTADOR", "EMITENTE DA NFS-E", "FORNECEDOR"):
        pos = upper.find(keyword)
        if pos >= 0:
            trecho = texto[pos:pos + 1800]
            for cnpj in _todos_cnpjs(trecho):
                if cnpj != company_cnpj:
                    return cnpj

    for cnpj in _todos_cnpjs(texto):
        if cnpj != company_cnpj and cnpj not in EMPRESAS:
            return cnpj
    for cnpj in _todos_cnpjs(texto):
        if cnpj != company_cnpj:
            return cnpj
    return ""


def _achar_nome_provider(texto: str, provider_cnpj: str) -> str:
    # DANFSe nacional: PRESTADOR / FORNECEDOR -> CNPJ -> Nome / Nome Empresarial -> valor.
    m = re.search(
        r"PRESTADOR\s*/\s*FORNECEDOR.*?Nome\s*/\s*Nome\s+Empresarial\s*\n\s*([^\n]{4,180})",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip()[:160]

    patterns = [
        r"(?:RAZ[AÃ]O SOCIAL|NOME EMPRESARIAL|NOME/RAZ[AÃ]O SOCIAL)\s*[:\-]?\s*([^\n]{4,160})",
        r"PRESTADOR(?:\s+DE\s+SERVI[CÇ]OS?)?\s*[:\-]?\s*\n?([^\n]{4,160})",
        r"EMITENTE\s*[:\-]?\s*\n?([^\n]{4,160})",
    ]
    nome = _match_primeiro(texto, patterns)
    if nome and not CNPJ_RE.search(nome):
        return nome.strip(" :-")[:160]

    if not provider_cnpj:
        return ""

    linhas = _linhas(texto)
    provider_digits = re.sub(r"\D", "", provider_cnpj)
    for i, linha in enumerate(linhas):
        if provider_cnpj in linha or provider_digits in re.sub(r"\D", "", linha):
            candidatos = linhas[max(0, i - 8): min(len(linhas), i + 8)]
            for j, cand in enumerate(candidatos):
                norm = sem_acento(cand).upper()
                if "NOME / NOME EMPRESARIAL" in norm and j + 1 < len(candidatos):
                    return candidatos[j + 1][:160]
            for cand in candidatos:
                norm = sem_acento(cand).upper()
                if (
                    len(cand) >= 5
                    and not CNPJ_RE.search(cand)
                    and not DATE_RE.search(cand)
                    and not re.fullmatch(r"[\d\W]+", cand)
                    and not any(x in norm for x in ("CNPJ", "CPF", "INSCRICAO", "ENDERECO", "TELEFONE"))
                ):
                    return cand[:160]
    return ""



def _parece_nome_empresa(value: str) -> bool:
    norm = sem_acento(value).upper().strip()
    if len(norm) < 5:
        return False
    if CNPJ_RE.search(value) or DATE_RE.search(value):
        return False
    if re.fullmatch(r"[\d\W]+", value):
        return False
    proibidas = (
        "CNPJ", "CPF", "CEP", "TEL", "INSCR", "VALOR", "VENCIMENTO", "EMISSAO",
        "AUTENTICACAO", "FICHA", "PAGAVEL", "INSTRUCOES", "NOSSO NUMERO", "DOCUMENTO",
        "DOC. EMITIDO", "SIMPLES NACIONAL", "NAO GERA DIREITO",
    )
    if any(x in norm for x in proibidas):
        return False
    if re.search(r"\b(LTDA|EPP|EIRELI|COMERCIO|SERVICOS?|SISTEMAS?|ME)\b", norm):
        return True
    if re.search(r"\bS/?A\b", norm):
        return True
    return False


def _achar_nome_provider_recibo(texto: str, provider_cnpj: str) -> str:
    """Prioriza o nome que aparece no recibo/boleto junto ao CNPJ do cedente."""
    if not provider_cnpj:
        return ""
    linhas = _linhas(texto)
    provider_digits = re.sub(r"\D", "", provider_cnpj)

    # O layout do RECIBO normalmente repete o cedente no fim do boleto. Ali o nome
    # aparece imediatamente antes do CNPJ e e a referencia mais confiavel.
    for i in range(len(linhas) - 1, -1, -1):
        linha = linhas[i]
        if provider_cnpj not in linha and provider_digits not in re.sub(r"\D", "", linha):
            continue
        for j in range(i - 1, max(-1, i - 26), -1):
            cand = linhas[j].strip()
            if _parece_nome_empresa(cand):
                return cand[:160]

    return _achar_nome_provider(texto, provider_cnpj)


def _achar_descricao_recibo(texto: str) -> str:
    linhas = _linhas(texto)
    # No recibo usado pelo processo, a descricao costuma aparecer no inicio do
    # texto extraido, antes dos rotulos do cabecalho.
    for linha in linhas[:18]:
        norm = sem_acento(linha).upper()
        if len(linha) < 12:
            continue
        if any(x in norm for x in ("RECIBO DA NOTA", "CLIENTE", "CNPJ", "CEP", "DESCRICAO DOS SERVICOS")):
            continue
        if re.search(r"\b(LTDA|EPP|S/A|S\.?A\.?|EIRELI)\b", norm):
            continue
        if MONEY_RE.fullmatch(linha) or DATE_RE.search(linha):
            continue
        if re.fullmatch(r"[\d\W]+", linha):
            continue
        return linha[:1200]
    return ""

def _achar_numero_nota(texto: str) -> str:
    """Extrai o numero fiscal sem confundir inscricao municipal/RPS.

    Alguns layouts (ex.: NFS-e da Prefeitura de Sao Paulo) imprimem o valor
    *antes* do rotulo ``Numero da Nota``. Por isso a leitura por linhas e
    feita antes dos regex genericos.
    """
    linhas = _linhas(texto)
    for i, linha in enumerate(linhas):
        norm = sem_acento(linha).upper().strip()
        if norm in {"NUMERO DA NOTA", "NUMERO DA NFS-E", "NUMERO DA NFSE", "Nº NFS-E", "N° NFS-E", "NO NFS-E"}:
            # Primeiro procura imediatamente depois do rotulo. Alguns recibos
            # colocam 1a VIA e DATA EMISSAO entre o rotulo e o numero.
            for j in range(i + 1, min(len(linhas), i + 9)):
                cand = linhas[j].strip()
                if re.fullmatch(r"0*\d{3,14}", cand):
                    return cand.lstrip("0") or "0"
            # Alguns PDFs extraem cabecalho em ordem visual e deixam o numero antes.
            for j in range(i - 1, max(-1, i - 5), -1):
                cand = linhas[j].strip()
                if re.fullmatch(r"0*\d{3,14}", cand):
                    return cand.lstrip("0") or "0"

    patterns = [
        r"N[UÚ]MERO\s+DA\s+NFS[- ]?E\s*\n\s*(\d+)",
        r"N[UÚ]MERO\s+DA\s+NFS[- ]?E\s*[:\-]?\s*(\d+)",
        r"N[UÚ]MERO\s+(?:DA\s+)?NOTA\s*[:\-]?\s*(\d+)",
    ]
    value = _match_primeiro(texto, patterns)
    return value.lstrip("0") or ("0" if value else "")


def _achar_numero_rps(texto: str) -> str:
    """Extrai o RPS, usado por alguns fornecedores para referenciar o boleto."""
    value = _match_primeiro(
        texto,
        [
            r"RPS\s*N[°ºO.]?\s*[:\-]?\s*([0-9.]{3,20})",
            r"N[UÚ]MERO\s+RPS\s*[:\-]?\s*\n?\s*([0-9.]{3,20})",
        ],
    )
    digits = re.sub(r"\D", "", value or "")
    return digits.lstrip("0") or ("0" if digits else "")


def _normalizar_documento_base(value: str) -> str:
    """Normaliza referencias como 991483-01, 76197/1 e 0000047745."""
    raw = (value or "").strip()
    if not raw:
        return ""
    m = re.fullmatch(r"0*(\d{4,14})[-/]0*(\d{1,3})", raw)
    if m:
        return m.group(1).lstrip("0") or "0"
    digits = re.sub(r"\D", "", raw)
    return digits.lstrip("0") or ("0" if digits else "")

def _achar_emissao(texto: str) -> str:
    debit = _achar_emissao_nota_debito(texto)
    if debit:
        return debit
    patterns = [
        r"DATA\s+E\s+HORA\s+DA\s+EMISS[AÃ]O\s+DA\s+NFS[- ]?E\s*\n\s*(\d{2}[/-]\d{2}[/-]\d{4})",
        r"DATA\s+(?:E\s+HORA\s+)?(?:DA\s+)?EMISS[AÃ]O(?:\s+DA\s+NFS[- ]?E)?\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
        r"EMISS[AÃ]O\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
        r"EMITID[AO]\s+EM\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
    ]
    return data_iso(_match_primeiro(texto, patterns))


def _achar_valor(texto: str) -> str:
    debit = _achar_valor_nota_debito(texto)
    if debit:
        return debit
    patterns = [
        r"VALOR\s+L[IÍ]QUIDO\s+A\s+SER\s+PAGO\s*[:\-]?\s*(?:R\$\s*)?([\d.]+,\d{2})",
        r"VALOR\s+TOTAL\s+DOS\s+SERVI[CÇ]OS\s*=\s*(?:R\$\s*)?([\d.]+,\d{2})",
        r"VALOR\s+TOTAL\s+COBRADO\s*=\s*(?:R\$\s*)?([\d.]+,\d{2})",
        r"VALOR\s+DA\s+OPERA[CÇ][AÃ]O\s*/\s*SERVI[CÇ]O\s*\n\s*R\$\s*([\d.]+,\d{2})",
        r"VALOR\s+L[IÍ]QUIDO\s+DA\s+NFS[- ]?E\s*\n\s*R\$\s*([\d.]+,\d{2})",
        r"VALOR\s+TOTAL\s+(?:DA\s+)?(?:NOTA|NFS[- ]?E).*?(?:R\$\s*)?([\d.]+,\d{2})",
        r"VALOR\s+DOS\s+SERVI[CÇ]OS.*?(?:R\$\s*)?([\d.]+,\d{2})",
    ]
    return _match_primeiro(texto, patterns, re.IGNORECASE | re.MULTILINE | re.DOTALL)

def _datas_proximas_ao_rotulo(texto: str, rotulo: str) -> list[str]:
    linhas = _linhas(texto)
    resultados: list[tuple[int, str]] = []
    for i, linha in enumerate(linhas):
        if rotulo in sem_acento(linha).upper():
            for delta in range(-3, 5):
                j = i + delta
                if 0 <= j < len(linhas):
                    m = DATE_RE.search(linhas[j])
                    if m:
                        resultados.append((abs(delta), m.group(0)))
    resultados.sort(key=lambda x: x[0])
    return [x[1] for x in resultados]


def _achar_vencimento(texto: str) -> str:
    boleto = _achar_vencimento_boleto(texto)
    if boleto:
        return boleto
    patterns = [
        r"(\d{2}[/-]\d{2}[/-]\d{4})\s*\n\s*VENCIMENTO\b",
        r"VENCIMENTO\s*[:\-]?\s*\n?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
        r"DATA\s+DE\s+VENCIMENTO\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
        r"VENC\.\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
    ]
    value = _match_primeiro(texto, patterns)
    if value:
        return data_iso(value)

    proximas = _datas_proximas_ao_rotulo(texto, "VENCIMENTO")
    return data_iso(proximas[0]) if proximas else ""


def _achar_competencia(texto: str) -> str:
    value = _match_primeiro(
        texto,
        [
            r"COMPET[EÊ]NCIA\s+DA\s+NFS[- ]?E\s*\n\s*(\d{2}[/-]\d{2}[/-]\d{4})",
            r"COMPET[EÊ]NCIA(?:\s+DA\s+NFS[- ]?E)?\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})",
            r"COMPET[EÊ]NCIA\s*[:\-]?\s*(\d{2}[/-]\d{4})",
        ],
    )
    return value


def _achar_chave_acesso_nfse(texto: str) -> str:
    value = _match_primeiro(
        texto,
        [
            r"CHAVE\s+DE\s+ACESSO\s+DA\s+NFS[- ]?E\s*\n\s*(\d{44,60})",
            r"N[°º]\s*NFS[- ]?E\s*/\s*CHAVE\s+NFS[- ]?E\s*\n\s*\d+\s*/\s*(\d{44,60})",
        ],
    )
    if value:
        return value
    for item in NFSE_KEY_RE.findall(texto):
        if len(item) >= 44:
            return item
    return ""


def _achar_numero_dps(texto: str) -> str:
    return _match_primeiro(texto, [r"N[UÚ]MERO\s+DA\s+DPS\s*\n\s*(\d+)"])


def _achar_serie_dps(texto: str) -> str:
    return _match_primeiro(texto, [r"S[ÉE]RIE\s+DA\s+DPS\s*\n\s*([A-Z0-9.\-/]+)"])


def _achar_codigo_tributacao(texto: str) -> str:
    return _match_primeiro(
        texto,
        [r"C[ÓO]DIGO\s+DE\s+TRIBUTA[CÇ][AÃ]O\s+NACIONAL/MUNICIPAL\s*\n\s*([0-9.]+(?:\s*/\s*[^\n]+)?)"],
    )


def _achar_codigo_nbs(texto: str) -> str:
    return _match_primeiro(texto, [r"C[ÓO]DIGO\s+DA\s+NBS\s*\n\s*([0-9.]+)"])


def _achar_descricao_servico(texto: str) -> str:
    debit = _achar_descricao_nota_debito(texto)
    if debit:
        return debit
    # DANFSe nacional possui um bloco muito bem definido.
    value = _match_primeiro(
        texto,
        [
            r"Descri[cç][aã]o\s+do\s+Servi[cç]o\s*\n\s*([^\n]{3,1000})",
            r"Descri[cç][aã]o\s+dos\s+Servi[cç]os\s*\n\s*([^\n]{3,1000})",
        ],
    )
    if value:
        return value[:1200]

    # Fallback para layouts que trazem o texto em um bloco apos o marcador.
    upper = sem_acento(texto).upper()
    for marcador in ("DISCRIMINACAO DOS SERVICOS", "DESCRICAO DOS SERVICOS"):
        pos = upper.find(marcador)
        if pos >= 0:
            trecho = texto[pos + len(marcador): pos + len(marcador) + 1500]
            fim = sem_acento(trecho).upper().find("TRIBUTACAO")
            if fim > 0:
                trecho = trecho[:fim]
            linhas = [x.strip(" :-\t") for x in trecho.splitlines() if x.strip(" :-\t")]
            if linhas:
                return " ".join(linhas[:8])[:1200]
    return ""


def _achar_pagamento_tipo(texto: str) -> str:
    upper = sem_acento(texto).upper()
    if "PIX" in upper:
        return "PIX"
    if "FICHA DE COMPENSACAO" in upper or "PAGAVEL EM QUALQUER BANCO" in upper or _achar_linha_digitavel(texto):
        return "BOLETO"
    return ""


def _achar_meio_pagamento_descricao(texto: str) -> str:
    """Retorna a descricao textual do meio de pagamento quando o PDF a declara.

    Ex.: ``Boleto Bancário Bradesco``. Mantemos o texto do documento para que
    a observacao herdada do mes anterior possa ser atualizada sem inventar
    nomenclatura.
    """
    value = _match_primeiro(
        texto,
        [
            r"MEIO\s+DE\s+PAGAMENTO\s*[:\-]?\s*([^\n\r]{2,120})",
            r"FORMA\s+DE\s+PAGAMENTO\s*[:\-]?\s*([^\n\r]{2,120})",
        ],
        re.IGNORECASE | re.MULTILINE,
    )
    if value:
        value = re.sub(r"\s+", " ", value).strip(" .;-\t")
        # Evita carregar textos subsequentes quando a extracao juntou colunas.
        for marker in ("VALOR", "VENCIMENTO", "CLIENTE", "BENEFICIARIO"):
            pos = sem_acento(value).upper().find(marker)
            if pos > 3:
                value = value[:pos].rstrip(" :-")
        return value[:120]
    return ""


def _achar_referencia_periodo(texto: str) -> str:
    """Extrai referencias mensais como ``Julho/2026`` quando existirem."""
    meses = (
        "JANEIRO|FEVEREIRO|MARCO|MARÇO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|"
        "SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO"
    )
    value = _match_primeiro(
        texto,
        [
            rf"\bREF\.?\s*[:\-]?\s*({meses})\s*/\s*(\d{{4}})",
            rf"\bREFER[EÊ]NCIA\s*[:\-]?\s*({meses})\s*/\s*(\d{{4}})",
            rf"\bREFERENTE\s+A\s*[:\-]?\s*({meses})\s*/\s*(\d{{4}})",
        ],
        re.IGNORECASE | re.MULTILINE,
    )
    if value:
        # _match_primeiro devolve apenas group(1); para mes/ano usamos busca direta.
        pass
    normalized = sem_acento(texto).upper()
    m = re.search(
        r"\b(?:REF\.?|REFERENCIA|REFERENTE\s+A)\s*[:\-]?\s*"
        r"(JANEIRO|FEVEREIRO|MARCO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)"
        r"\s*/\s*(\d{4})",
        normalized,
        re.IGNORECASE,
    )
    if not m:
        return ""
    mapa = {
        "JANEIRO": "Janeiro", "FEVEREIRO": "Fevereiro", "MARCO": "Março",
        "ABRIL": "Abril", "MAIO": "Maio", "JUNHO": "Junho",
        "JULHO": "Julho", "AGOSTO": "Agosto", "SETEMBRO": "Setembro",
        "OUTUBRO": "Outubro", "NOVEMBRO": "Novembro", "DEZEMBRO": "Dezembro",
    }
    return f"{mapa.get(m.group(1).upper(), m.group(1).title())}/{m.group(2)}"


def _achar_linha_digitavel(texto: str) -> str:
    # Procura linha que, removendo pontuacao, tenha exatamente 47 ou 48 digitos.
    for linha in _linhas(texto):
        digits = re.sub(r"\D", "", linha)
        if len(digits) not in (47, 48):
            continue
        # Evita confundir a chave de acesso da NFS-e (normalmente apenas digitos).
        if re.fullmatch(r"\d{47,48}", linha.strip()):
            continue
        if not re.fullmatch(r"[\d.\-\s]+", linha.strip()):
            continue
        return re.sub(r"\s+", " ", linha).strip()
    return ""


def _achar_valor_pagamento(texto: str) -> str:
    # Primeiro usa rotulos de valor explicitamente associados ao pagamento.
    patterns = [
        r"VALOR\s+(?:A\s+)?PAGAR\s*[:\-]?\s*\n?\s*R\$?\s*([\d.]+,\d{2})",
        r"VALOR\s+(?:DO\s+)?T[IÍ]TULO\s*[:\-]?\s*\n?\s*(?:R\$\s*)?([\d.]+,\d{2})",
        r"VALOR\s+(?:DO\s+)?DOCUMENTO(?:\s+EM\s+R\$)?\s*[:\-]?\s*\n?\s*(?:R\$\s*)?([\d.]+,\d{2})",
        r"\(=\)\s*Valor\s+do\s+Documento(?:\s+em\s+R\$)?\s*\n?\s*(?:R\$\s*)?([\d.]+,\d{2})",
    ]
    value = _match_primeiro(texto, patterns, re.IGNORECASE | re.MULTILINE)
    if value:
        return value

    # Em muitos boletos o PDF extrai primeiro todos os rotulos e depois os valores.
    # Nesses layouts o valor principal costuma ser repetido (recibo + ficha). Escolhe
    # o valor monetario mais frequente e, em empate, o maior.
    from collections import Counter
    valores = MONEY_RE.findall(texto)
    if valores:
        cont = Counter(valores)
        ordenados = sorted(
            cont.items(),
            key=lambda kv: (kv[1], _valor_float(kv[0]) or 0.0),
            reverse=True,
        )
        if ordenados:
            return ordenados[0][0]

    # Fallback controlado perto do vencimento.
    venc = _achar_vencimento(texto)
    if venc:
        venc_br = datetime.strptime(venc, "%Y-%m-%d").strftime("%d/%m/%Y")
        for pos in [m.start() for m in re.finditer(re.escape(venc_br), texto)]:
            trecho = texto[pos:pos + 350]
            m = re.search(r"(?:VALOR(?:\s+A\s+PAGAR)?[^\n]{0,80}\n?\s*)?R\$\s*([\d.]+,\d{2})", trecho, re.I)
            if m:
                return m.group(1)
    return ""

def _achar_banco(texto: str) -> tuple[str, str]:
    upper = sem_acento(texto).upper()
    bancos = [
        ("341", "Itau"),
        ("237", "Bradesco"),
        ("033", "Santander"),
        ("001", "Banco do Brasil"),
        ("104", "Caixa Economica Federal"),
        ("756", "Sicoob"),
        ("748", "Sicredi"),
        ("077", "Banco Inter"),
    ]

    nomes = [
        ("ITAU", "341", "Itau"),
        ("BRADESCO", "237", "Bradesco"),
        ("SANTANDER", "033", "Santander"),
        ("BANCO DO BRASIL", "001", "Banco do Brasil"),
        ("CAIXA ECONOMICA", "104", "Caixa Economica Federal"),
        ("SICOOB", "756", "Sicoob"),
        ("SICREDI", "748", "Sicredi"),
        ("BANCO INTER", "077", "Banco Inter"),
    ]
    for palavra, codigo, nome in nomes:
        if palavra in upper:
            return nome, codigo

    # Codigo do banco aparece normalmente como 341-7, 237-2 etc.
    for codigo, nome in bancos:
        if re.search(rf"(?<!\d){re.escape(codigo)}-\d(?!\d)", texto):
            return nome, codigo

    linha = _achar_linha_digitavel(texto)
    if linha:
        digits = re.sub(r"\D", "", linha)
        for codigo, nome in bancos:
            if digits.startswith(codigo):
                return nome, codigo
    return "", ""


def _achar_beneficiario(texto: str, provider_cnpj: str, provider_name: str) -> tuple[str, str]:
    cnpjs = _todos_cnpjs(texto)
    if provider_cnpj and provider_cnpj in cnpjs:
        return provider_name, provider_cnpj

    # Em boleto, o tomador/pagador costuma ser uma empresa interna; o outro CNPJ tende
    # a ser o beneficiario.
    for cnpj in cnpjs:
        if cnpj not in EMPRESAS:
            return "", cnpj
    return "", ""


def _achar_pix_chave(texto: str) -> str:
    return _match_primeiro(
        texto,
        [
            r"CHAVE\s+PIX\s*[:\-]?\s*([^\n]{3,160})",
            r"PIX\s+COPIA\s+E\s+COLA\s*[:\-]?\s*([^\n]{10,250})",
        ],
    )[:250]


def _achar_pagamento_emissao(texto: str) -> str:
    # Prioriza o bloco do boleto, que geralmente traz Data Emissao em seguida.
    lines = _linhas(texto)
    for i, line in enumerate(lines):
        if sem_acento(line).upper() in {"DATA EMISSAO", "DATA DE EMISSAO"}:
            for j in range(i + 1, min(i + 25, len(lines))):
                m = DATE_RE.search(lines[j])
                if m:
                    return data_iso(m.group(0))
    return ""


def _achar_numero_documento_pagamento(texto: str) -> str:
    # Quando o documento declara uma FATURA, esse e o identificador operacional
    # mais util para observacoes e conciliacao (ex.: FINNET 23433).
    fatura = _match_primeiro(
        texto,
        [r"\bFATURA\s*[:\-]?\s*0*(\d{3,20})\b"],
        re.IGNORECASE | re.MULTILINE,
    )
    if fatura:
        return fatura

    # Documentos parcelados como 991483-01 e 76197/1 sao referencias fortes.
    for linha in _linhas(texto):
        cand = linha.strip()
        if re.fullmatch(r"0*\d{5,12}[-/]0*\d{1,3}", cand):
            sufixo = re.split(r"[-/]", cand)[-1]
            # Parcela real: /1, -01 etc. CEPs como 77804-010 nao entram.
            if len(sufixo) <= 2 and int(sufixo or "0") <= 12:
                return cand

    inline = _match_primeiro(
        texto,
        [
            r"N[º°o.]?\s*do\s+Documento\s*[:\-]?\s*([0-9][0-9./-]{3,20})",
            r"Numero\s+do\s+Documento\s*[:\-]?\s*([0-9][0-9./-]{3,20})",
        ],
    )
    if inline:
        return inline.strip()

    # Layout Auditor/Itau legado.
    m = re.search(
        r"C[óo]digo\s+de\s+Baixa\s*\n\s*\d{2}/\d{2}/\d{4}\s*\n\s*([^\n]+)",
        texto,
        re.IGNORECASE,
    )
    if m and re.search(r"\d", m.group(1)):
        return m.group(1).strip()

    value = _achar_numero_documento_boleto_por_frequencia(texto)
    return value.lstrip("0") or ("0" if value else "")

def _achar_nosso_numero(texto: str) -> str:
    inline = _match_primeiro(
        texto,
        [
            r"NOSSO\s+N[UÚ]MERO\s*[:\-]?\s*([0-9][0-9./-]{3,24})",
            r"NOSSO\s+NUMERO\s*[:\-]?\s*([0-9][0-9./-]{3,24})",
        ],
        re.IGNORECASE | re.MULTILINE,
    )
    if inline:
        return inline.strip()

    # Em alguns PDFs a ordem de extracao separa os rotulos dos valores.
    # Entre os codigos com digito verificador, o Nosso Numero normalmente possui
    # mais digitos que o codigo do cedente/convenio. No exemplo: 00006183-6.
    matches = re.findall(r"(?<!\d)(\d{5,12}-\d)(?!\d)", texto)
    if not matches:
        return ""
    return max(matches, key=lambda x: len(re.sub(r"\D", "", x)))


def _valor_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(".", "").replace(",", "."))
    except Exception:
        return None


def _achar_referencia_nota_no_pagamento(texto: str) -> tuple[str, str, str, str, str]:
    """Extrai referencias apenas quando o PDF possui bloco real de pagamento.

    Evita interpretar textos fiscais que apenas mencionam a palavra "boleto" como
    se fossem boletos completos (caso SKYTEF).
    """
    upper = sem_acento(texto).upper()
    strong_payment = any(
        marker in upper
        for marker in (
            "FICHA DE COMPENSACAO",
            "RECIBO DO PAGADOR",
            "LOCAL DE PAGAMENTO",
            "NOSSO NUMERO",
        )
    )
    if not strong_payment:
        return "", "", "", "", ""

    numero = _achar_nota_fiscal_referenciada_boleto(texto)
    linhas = _linhas(texto)
    for i, linha in enumerate(linhas):
        if numero:
            break
        norm = sem_acento(linha).upper()
        if "Nº NFS-E" in norm or "N° NFS-E" in norm or norm == "NFS-E":
            trecho = linhas[i:i + 12]
            for cand in trecho:
                if re.fullmatch(r"0*\d{3,20}", cand):
                    numero = cand.lstrip("0") or "0"
                    break
            if numero:
                break

    emissao = _achar_pagamento_emissao(texto) or _achar_emissao(texto)
    valor = _achar_valor_pagamento(texto)

    cnpjs = _todos_cnpjs(texto)
    company_cnpj = next((c for c in cnpjs if c in EMPRESAS), "")
    provider_cnpj = next((c for c in cnpjs if c != company_cnpj and c not in EMPRESAS), "")
    return numero, emissao, valor, provider_cnpj, company_cnpj

def validar_consistencia(dados: NotaDados, texto_nfse: str = "") -> list[str]:
    """Compara os dados operacionais do recibo/boleto com a NFS-e oficial.

    A partir da v4 o recibo/boleto e a fonte primaria do preenchimento. A NFS-e
    oficial fica como validacao e como anexo fiscal.
    """
    avisos: list[str] = []
    if not texto_nfse:
        return avisos

    nf_company_cnpj, _, _ = _achar_empresa_interna(texto_nfse)
    nf_provider_cnpj = _achar_provider_cnpj(texto_nfse, nf_company_cnpj)
    nf_numero = _achar_numero_nota(texto_nfse)
    nf_emissao = _achar_emissao(texto_nfse)
    nf_valor = _achar_valor(texto_nfse)

    if nf_numero and dados.numero and nf_numero != dados.numero:
        avisos.append(f"Numero da NFS-e diverge: recibo/boleto {dados.numero} x NFS-e oficial {nf_numero}.")
    if nf_emissao and dados.emissao and nf_emissao != dados.emissao:
        avisos.append("Data de emissao diverge entre o recibo/boleto e a NFS-e oficial.")
    if nf_valor and dados.valor:
        a, b = _valor_float(nf_valor), _valor_float(dados.valor)
        if a is not None and b is not None and abs(a - b) > 0.01:
            avisos.append("Valor diverge entre o recibo/boleto e a NFS-e oficial.")
    if nf_provider_cnpj and dados.provider_cnpj and nf_provider_cnpj != dados.provider_cnpj:
        avisos.append("CNPJ do fornecedor diverge entre o recibo/boleto e a NFS-e oficial.")
    if nf_company_cnpj and dados.company_cnpj and nf_company_cnpj != dados.company_cnpj:
        avisos.append("CNPJ da empresa/tomador diverge entre o recibo/boleto e a NFS-e oficial.")
    return avisos


def extrair_dados(nota_pdf: str | Path, pagamento_pdf: str | Path) -> tuple[NotaDados, str, str]:
    """Extrai os dados usando o RECIBO/Boleto como fonte primaria.

    O arquivo com 'RECIBO DA NOTA FISCAL DE SERVICOS ELETRONICA' contem os dados
    usados no lancamento: numero, emissao, valor, fornecedor, empresa e vencimento.
    A NFS-e oficial e usada como validacao e como anexo fiscal.
    """
    texto_nfse = ler_pdf(nota_pdf)
    texto_pagamento = ler_pdf(pagamento_pdf)

    # Empresa/tomador vem primeiro do recibo/boleto; a NFS-e oficial e fallback.
    company_cnpj, company_id, company_name = _achar_empresa_interna(texto_pagamento)
    if not company_cnpj:
        company_cnpj, company_id, company_name = _achar_empresa_interna(texto_nfse)

    # CNPJ do fornecedor: regra solicitada - fonte primaria e o RECIBO/Boleto.
    ref_numero, ref_emissao, ref_valor, ref_provider, ref_company = _achar_referencia_nota_no_pagamento(
        texto_pagamento
    )
    provider_cnpj = ref_provider or _achar_provider_cnpj(texto_pagamento, company_cnpj)
    if not provider_cnpj:
        provider_cnpj = _achar_provider_cnpj(texto_nfse, company_cnpj)

    provider_name = _achar_nome_provider_recibo(texto_pagamento, provider_cnpj)
    if not provider_name:
        provider_name = _achar_nome_provider(texto_nfse, provider_cnpj)

    banco, banco_codigo = _achar_banco(texto_pagamento)
    beneficiario_nome, beneficiario_cnpj = _achar_beneficiario(
        texto_pagamento, provider_cnpj, provider_name
    )

    numero = (
        ref_numero
        or _achar_referencia_documento(texto_pagamento)
        or _achar_referencia_documento(texto_nfse)
    )
    emissao = (
        _achar_pagamento_emissao(texto_pagamento)
        or ref_emissao
        or _achar_emissao(texto_pagamento)
        or _achar_emissao(texto_nfse)
    )
    valor_pagamento = _achar_valor_pagamento(texto_pagamento)
    score_nf_nota, score_nf_pag = _score_documento(texto_nfse)
    score_pg_nota, score_pg_pag = _score_documento(texto_pagamento)
    mesmo_arquivo = Path(nota_pdf).resolve() == Path(pagamento_pdf).resolve()
    if mesmo_arquivo and score_nf_nota > score_nf_pag:
        # Documento fiscal unico: nao deixa heuristicas de boleto (0,00, juros etc.)
        # sobreporem o valor fiscal principal.
        valor = _achar_valor(texto_nfse) or ref_valor or valor_pagamento
    elif score_pg_pag > score_pg_nota:
        valor = ref_valor or valor_pagamento or _achar_valor(texto_pagamento) or _achar_valor(texto_nfse)
    else:
        valor = _achar_valor(texto_pagamento) or _achar_valor(texto_nfse) or ref_valor or valor_pagamento

    dados = NotaDados(
        # Fonte primaria: RECIBO DA NOTA FISCAL / boleto.
        numero=numero,
        valor=valor,
        emissao=emissao,
        provider_cnpj=provider_cnpj,
        provider_name=provider_name,
        company_cnpj=company_cnpj or ref_company,
        company_id=company_id,
        company_name=company_name,
        vencimento=_achar_vencimento(texto_pagamento) or _achar_vencimento(texto_nfse),
        descricao_servico=(
            _achar_descricao_nota_debito(texto_pagamento)
            or _achar_descricao_nota_debito(texto_nfse)
            or _achar_descricao_recibo(texto_pagamento)
            or _achar_descricao_servico(texto_nfse)
        ),

        # Dados fiscais complementares ficam preferencialmente na NFS-e oficial.
        competencia=_achar_competencia(texto_nfse),
        chave_acesso_nfse=_achar_chave_acesso_nfse(texto_nfse),
        numero_dps=_achar_numero_dps(texto_nfse),
        serie_dps=_achar_serie_dps(texto_nfse),
        codigo_tributacao=_achar_codigo_tributacao(texto_nfse),
        codigo_nbs=_achar_codigo_nbs(texto_nfse),

        # Dados de pagamento.
        pagamento_tipo=_achar_pagamento_tipo(texto_pagamento),
        pagamento_meio_descricao=(
            _achar_meio_pagamento_descricao(texto_pagamento)
            or _achar_meio_pagamento_descricao(texto_nfse)
        ),
        referencia_periodo=(
            _achar_referencia_periodo(texto_pagamento)
            or _achar_referencia_periodo(texto_nfse)
        ),
        pagamento_valor=valor_pagamento,
        pagamento_emissao=_achar_pagamento_emissao(texto_pagamento),
        pagamento_numero_documento=_achar_numero_documento_pagamento(texto_pagamento),
        banco=banco,
        banco_codigo=banco_codigo,
        linha_digitavel=_achar_linha_digitavel(texto_pagamento),
        nosso_numero=_achar_nosso_numero(texto_pagamento),
        beneficiario_nome=beneficiario_nome,
        beneficiario_cnpj=beneficiario_cnpj,
        pix_chave=_achar_pix_chave(texto_pagamento),
    )

    # Caso a empresa tenha sido identificada apenas por ref_company, completa o ID.
    if not dados.company_id and dados.company_cnpj in EMPRESAS:
        dados.company_id, dados.company_name = EMPRESAS[dados.company_cnpj]

    return dados, texto_nfse, texto_pagamento

