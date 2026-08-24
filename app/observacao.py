from __future__ import annotations

import re
from datetime import datetime

RATEIO_RE = re.compile(
    r"(?im)^\s*-?\s*ONDE\s+FOI\s+UTILIZADO\s+ESTA\s+COMPRA\s*\(RATEIO\)\s*:\s*"
)
DATE_BR_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")


# Bancos que o parser do PDF ja identifica. Mantemos os nomes aqui somente
# para trocar o banco dentro de linhas de pagamento da observacao anterior.
_BANK_NAMES_RE = re.compile(
    r"(?i)\b(?:Itau|Itaú|Bradesco|Santander|Banco\s+do\s+Brasil|"
    r"Caixa\s+Economica\s+Federal|Caixa\s+Econ[oô]mica\s+Federal|Sicoob|Sicredi|Banco\s+Inter)\b"
)


def data_br(data_iso_value: str) -> str:
    value = (data_iso_value or "").strip()
    if not value:
        return ""

    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return value


def extrair_rateio(observacao: str) -> str:
    """Extrai somente o conteudo abaixo do bloco de RATEIO da nota-base."""
    obs = (observacao or "").strip()
    if not obs:
        return ""
    match = RATEIO_RE.search(obs)
    if not match:
        return ""
    return obs[match.end():].strip()


def tem_bloco_rateio(observacao: str) -> bool:
    return bool(RATEIO_RE.search(observacao or ""))


def _meio_pagamento_padrao(tipo_pagamento: str, banco: str) -> str:
    tipo = (tipo_pagamento or "").strip().upper()
    banco = (banco or "").strip()

    if tipo == "PIX":
        return "PIX"
    if tipo == "BOLETO":
        if banco:
            return f"Boleto Bancário {banco}"
        return "Boleto Bancário"
    return ""


def _preservar_sufixo_parenteses(valor_antigo: str, valor_novo: str) -> str:
    """Preserva observacoes operacionais do texto-base, ex.: '(Obter no DDA)'."""
    antigo = (valor_antigo or "").rstrip()
    novo = (valor_novo or "").strip()
    if not novo:
        return antigo

    # Captura apenas um sufixo parentetico no fim da linha. Nao carregamos o
    # conteudo principal antigo, pois ele pode conter banco ou meio de pagamento
    # desatualizado.
    m = re.search(r"(\s*\([^\r\n]*\)\s*)$", antigo)
    if m:
        return novo + m.group(1)
    return novo


def _substituir_data_em_linha(linha: str, vencimento_br: str) -> tuple[str, bool]:
    if not vencimento_br:
        return linha, False

    upper = linha.upper()
    # Atualiza datas somente em linhas claramente ligadas a pagamento/vencimento.
    # Isso evita trocar datas legitimas dentro do rateio ou de observacoes livres.
    if "VENCIMENTO" in upper or re.search(r"\bVENC\.?\b", upper):
        nova, n = DATE_BR_RE.subn(vencimento_br, linha)
        return nova, bool(n)

    # Padrao operacional antigo: "BOLETO 15/07/2026".
    if re.search(r"(?i)\bBOLETO\b", linha):
        nova, n = DATE_BR_RE.subn(vencimento_br, linha)
        return nova, bool(n)

    return linha, False


def _substituir_campo_rotulado(
    linha: str,
    rotulos: tuple[str, ...],
    novo_valor: str,
    *,
    prefixo_valor: str = "",
) -> tuple[str, bool]:
    if not novo_valor:
        return linha, False

    for rotulo in rotulos:
        pattern = re.compile(rf"(?i)(\b{rotulo}\b\s*[:\-]?\s*)(.*)$")
        m = pattern.search(linha)
        if not m:
            continue
        valor = f"{prefixo_valor}{novo_valor}" if prefixo_valor else novo_valor
        return linha[:m.start(2)] + valor, True
    return linha, False


def atualizar_observacao_com_pdf(
    observacao_base: str,
    *,
    vencimento_iso: str = "",
    tipo_pagamento: str = "",
    banco: str = "",
    meio_pagamento_descricao: str = "",
    referencia_periodo: str = "",
    pagamento_numero_documento: str = "",
    nosso_numero: str = "",
    pagamento_valor: str = "",
    numero_nota: str = "",
) -> str:
    """Reutiliza a observacao COMPLETA da nota-base e atualiza apenas dados confiaveis.

    A regra e propositalmente conservadora: mantemos texto livre, instrucoes como
    ``(Obter no DDA)`` e o rateio exatamente como estavam na nota anterior. So
    substituimos campos que estao explicitamente rotulados na observacao e que o
    PDF atual forneceu com seguranca.

    Campos tratados atualmente:
      * Data/Vencimento e padrao ``BOLETO dd/mm/aaaa``;
      * Meio de Pagamento, incluindo banco, preservando sufixos operacionais;
      * Ref./Referencia mensal quando o PDF trouxer esse dado;
      * Numero do Documento, Nosso Numero e Valor do Documento/Valor a Pagar;
      * Numero da Nota/NFS-e quando existir um rotulo explicito.
    """
    obs = (observacao_base or "").strip()
    if not obs:
        return montar_observacao(vencimento_iso, "", tipo_pagamento)

    venc = data_br(vencimento_iso)
    meio = (meio_pagamento_descricao or "").strip()
    if not meio:
        meio = _meio_pagamento_padrao(tipo_pagamento, banco)

    linhas = obs.splitlines()
    resultado: list[str] = []

    for linha_original in linhas:
        linha = linha_original

        # 1) Vencimento. A substituicao e restrita a linhas de pagamento.
        linha, _ = _substituir_data_em_linha(linha, venc)

        # 2) Meio de pagamento. Preserva sufixos como "(Obter no DDA)".
        m_meio = re.search(r"(?i)(\bMEIO\s+DE\s+PAGAMENTO\b\s*[:\-]?\s*)(.*)$", linha)
        if m_meio and meio:
            antigo = m_meio.group(2)
            novo = _preservar_sufixo_parenteses(antigo, meio)
            linha = linha[:m_meio.start(2)] + novo
        elif meio and re.search(r"(?i)^\s*BOLETO\b", linha):
            # Nos modelos antigos que usam "BOLETO 15/07/2026", mantemos a
            # estrutura e apenas trocamos o banco se ele ja estiver escrito.
            if banco and _BANK_NAMES_RE.search(linha):
                linha = _BANK_NAMES_RE.sub(banco, linha, count=1)

        # 3) Referencia mensal, quando o proprio PDF atual a informa.
        if referencia_periodo:
            m_ref = re.search(
                r"(?i)(\b(?:REF\.?|REFER[EÊ]NCIA|REFERENTE\s+A)\s*[:\-]?\s*)([A-Za-zÀ-ÿ]+\s*/\s*\d{4}|\d{2}\s*/\s*\d{4})",
                linha,
            )
            if m_ref:
                linha = linha[:m_ref.start(2)] + referencia_periodo + linha[m_ref.end(2):]

        # 4) Identificadores de pagamento, somente se o rotulo ja existir.
        linha, _ = _substituir_campo_rotulado(
            linha,
            (r"N[UÚ]MERO\s+DO\s+DOCUMENTO", r"N[º°]\s*DOCUMENTO", r"N[º°]\s+DO\s+DOCUMENTO"),
            pagamento_numero_documento,
        )
        linha, _ = _substituir_campo_rotulado(
            linha,
            (r"NOSSO\s+N[UÚ]MERO",),
            nosso_numero,
        )

        # 5) Valor do pagamento. Nao alteramos um "VALOR:" generico para nao
        # atingir valores de rateio ou observacoes livres.
        valor_formatado = pagamento_valor.strip()
        if valor_formatado:
            linha, _ = _substituir_campo_rotulado(
                linha,
                (r"VALOR\s+DO\s+DOCUMENTO", r"VALOR\s+A\s+PAGAR", r"VALOR\s+DO\s+T[IÍ]TULO"),
                valor_formatado,
                prefixo_valor="R$ ",
            )

        # 6) Numero fiscal, somente em rotulos inequivocos.
        linha, _ = _substituir_campo_rotulado(
            linha,
            (r"N[UÚ]MERO\s+DA\s+NOTA", r"NOTA\s+FISCAL", r"NFS[- ]?E"),
            numero_nota,
        )

        resultado.append(linha)

    return "\n".join(resultado).strip()


def montar_observacao(vencimento_iso: str, rateio: str = "", tipo_pagamento: str = "BOLETO") -> str:
    """Fallback para quando nao existe observacao-base no Agilize."""
    venc = data_br(vencimento_iso)
    tipo = (tipo_pagamento or "BOLETO").strip().upper()
    if tipo not in {"BOLETO", "PIX"}:
        tipo = "BOLETO"

    pagamento = tipo
    if venc:
        pagamento = f"{tipo} {venc}"

    rateio_limpo = (rateio or "").strip()
    return (
        "- DADOS PARA PAGAMENTO:\n"
        f"{pagamento}\n\n"
        "- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\n"
        f"{rateio_limpo}"
    ).rstrip()


def normalizar_observacao_base(
    observacao_base: str,
    vencimento_iso: str,
    tipo_pagamento: str = "BOLETO",
) -> str:
    """Compatibilidade: agora preserva a observacao inteira da nota anterior."""
    return atualizar_observacao_com_pdf(
        observacao_base,
        vencimento_iso=vencimento_iso,
        tipo_pagamento=tipo_pagamento,
    )


# Compatibilidade com modulos de versoes anteriores.
def atualizar_vencimento_observacao(observacao: str, vencimento_iso: str) -> str:
    return atualizar_observacao_com_pdf(observacao, vencimento_iso=vencimento_iso)
