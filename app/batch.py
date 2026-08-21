from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from models import NotaDados
from pdf_reader import (
    _achar_empresa_interna,
    _achar_fatura_generica,
    _achar_fatura_nota_debito,
    _achar_numero_dps,
    _achar_numero_documento_pagamento,
    _achar_numero_nota,
    _achar_numero_rps,
    _achar_nota_fiscal_referenciada_boleto,
    _achar_provider_cnpj,
    _achar_referencia_nota_no_pagamento,
    _achar_valor,
    _achar_valor_pagamento,
    _normalizar_documento_base,
    _score_documento,
    extrair_dados,
    ler_pdf,
    sem_acento,
)


@dataclass
class DocumentoInfo:
    path: Path
    texto: str
    numero_nfse: str = ""
    numero_fiscal: str = ""
    nota_referenciada: str = ""
    rps_numero: str = ""
    dps_numero: str = ""
    fatura_numero: str = ""
    pagamento_documento: str = ""
    pagamento_documento_base: str = ""
    score_nota: int = 0
    score_pagamento: int = 0
    company_cnpj: str = ""
    provider_cnpj: str = ""
    valor: str = ""
    tipo_hint: str = "documento"

    @property
    def papel(self) -> str:
        if self.score_nota > 0 and self.score_pagamento > 0 and abs(self.score_nota - self.score_pagamento) < 25:
            return "COMBINADO"
        if self.score_pagamento > self.score_nota:
            return "RECIBO / BOLETO"
        if self.score_nota > 0:
            return "NOTA FISCAL"
        return "DOCUMENTO"

    @property
    def is_nota(self) -> bool:
        return self.papel in {"NOTA FISCAL", "COMBINADO"}

    @property
    def is_pagamento(self) -> bool:
        return self.papel in {"RECIBO / BOLETO", "COMBINADO"}


@dataclass
class GrupoLancamento:
    key: str
    numero: str
    documentos: list[DocumentoInfo] = field(default_factory=list)
    nota_pdf: Optional[Path] = None
    pagamento_pdf: Optional[Path] = None
    conferencia_pdf: Optional[Path] = None
    dados: Optional[NotaDados] = None
    tipo_sugerido: str = "nfse"
    avisos: list[str] = field(default_factory=list)
    status: str = "Pronto"

    @property
    def paths(self) -> list[Path]:
        return [doc.path for doc in self.documentos]

    @property
    def empresa(self) -> str:
        if self.dados and self.dados.company_name:
            return self.dados.company_name
        return "Não identificada"

    @property
    def fornecedor_cnpj(self) -> str:
        return self.dados.provider_cnpj if self.dados else ""

    @property
    def resumo_documentos(self) -> str:
        qtd = len(self.documentos)
        return "1 PDF" if qtd == 1 else f"{qtd} PDFs"


def _tipo_sugerido(texto: str, score_nota: int, score_pagamento: int) -> str:
    upper = sem_acento(texto).upper()
    if "NOTA DE DEBITO" in upper:
        return "documentos"
    if (
        "NFS-E" in upper
        or "NFS E" in upper
        or "NOTA FISCAL DE SERVICOS" in upper
        or "NOTA FISCAL ELETRONICA DE SERVICOS" in upper
        or "NOTA FISCAL ELETRONICA DE SERVICO" in upper
    ):
        return "nfse"
    if (
        re.search(r"\bDANFE\b", upper)
        or re.search(r"\bNF-E\b", upper)
        or re.search(r"\bCT-E\b", upper)
        or "CONHECIMENTO DE TRANSPORTE" in upper
    ):
        return "nfe"
    if score_pagamento > 0:
        return "documentos"
    return "nfse"


def _norm_money(value: str) -> str:
    return re.sub(r"[^0-9]", "", value or "")


def _mesmo_valor(a: str, b: str) -> bool:
    if not a or not b:
        return True
    return _norm_money(a) == _norm_money(b)


def _numero_grupo(docs: list[DocumentoInfo]) -> str:
    # Sempre prefere o numero fiscal da nota. Depois usa referencias operacionais.
    for d in docs:
        if d.is_nota and d.numero_fiscal:
            return d.numero_fiscal
    for attr in ("nota_referenciada", "numero_fiscal", "fatura_numero", "pagamento_documento_base"):
        for d in docs:
            value = getattr(d, attr, "")
            if value:
                return value
    return ""


def analisar_documento(path: str | Path) -> DocumentoInfo:
    p = Path(path).resolve()
    texto = ler_pdf(p)
    score_nota, score_pagamento = _score_documento(texto)

    numero_fiscal = _achar_numero_nota(texto)
    nota_referenciada = _achar_nota_fiscal_referenciada_boleto(texto)
    rps = _achar_numero_rps(texto)
    dps = _achar_numero_dps(texto)
    fatura = _achar_fatura_nota_debito(texto) or _achar_fatura_generica(texto)
    pagamento_documento = _achar_numero_documento_pagamento(texto)
    pagamento_base = _normalizar_documento_base(pagamento_documento)

    ref_numero, _emissao, ref_valor, ref_provider, ref_company = _achar_referencia_nota_no_pagamento(texto)
    company_cnpj, _company_id, _company_name = _achar_empresa_interna(texto)
    company_cnpj = company_cnpj or ref_company
    provider_cnpj = ref_provider or _achar_provider_cnpj(texto, company_cnpj)

    if score_nota >= score_pagamento:
        valor = _achar_valor(texto) or ref_valor or _achar_valor_pagamento(texto)
    else:
        valor = ref_valor or _achar_valor_pagamento(texto) or _achar_valor(texto)

    numero = numero_fiscal or nota_referenciada or fatura or pagamento_base or ref_numero
    return DocumentoInfo(
        path=p,
        texto=texto,
        numero_nfse=numero,
        numero_fiscal=numero_fiscal,
        nota_referenciada=nota_referenciada or ref_numero,
        rps_numero=rps,
        dps_numero=dps,
        fatura_numero=fatura,
        pagamento_documento=pagamento_documento,
        pagamento_documento_base=pagamento_base,
        score_nota=score_nota,
        score_pagamento=score_pagamento,
        company_cnpj=company_cnpj,
        provider_cnpj=provider_cnpj,
        valor=valor,
        tipo_hint=_tipo_sugerido(texto, score_nota, score_pagamento),
    )


def _hard_veto(a: DocumentoInfo, b: DocumentoInfo) -> bool:
    # CNPJs diferentes sao uma prova forte de que os PDFs pertencem a cobrancas distintas.
    if a.provider_cnpj and b.provider_cnpj and a.provider_cnpj != b.provider_cnpj:
        return True
    if a.company_cnpj and b.company_cnpj and a.company_cnpj != b.company_cnpj:
        return True
    if a.valor and b.valor and not _mesmo_valor(a.valor, b.valor):
        return True
    return False


def _complementares(a: DocumentoInfo, b: DocumentoInfo) -> bool:
    return (a.is_nota and b.is_pagamento) or (b.is_nota and a.is_pagamento)


def _score_pareamento(a: DocumentoInfo, b: DocumentoInfo) -> tuple[int, str]:
    if _hard_veto(a, b):
        return -1000, "incompativel"

    score = 0
    razoes: list[str] = []
    comp = _complementares(a, b)

    # 1) Boleto que traz explicitamente NOTA FISCAL -> numero fiscal da nota.
    if a.nota_referenciada and b.numero_fiscal and a.nota_referenciada == b.numero_fiscal:
        score += 100; razoes.append("nota-referenciada")
    if b.nota_referenciada and a.numero_fiscal and b.nota_referenciada == a.numero_fiscal:
        score += 100; razoes.append("nota-referenciada")

    # 2) Mesmo numero fiscal entre nota e recibo/boleto combinado.
    if comp and a.numero_fiscal and b.numero_fiscal and a.numero_fiscal == b.numero_fiscal:
        score += 95; razoes.append("numero-fiscal")

    # 3) RPS da NFS-e -> numero do documento do boleto, removendo parcela (-01, /1).
    if a.rps_numero and b.is_pagamento and b.pagamento_documento_base and a.rps_numero == b.pagamento_documento_base:
        score += 92; razoes.append("rps-documento")
    if b.rps_numero and a.is_pagamento and a.pagamento_documento_base and b.rps_numero == a.pagamento_documento_base:
        score += 92; razoes.append("rps-documento")

    # 4) Fatura de nota de debito -> numero do documento do boleto.
    if a.fatura_numero and b.is_pagamento and b.pagamento_documento_base and a.fatura_numero == b.pagamento_documento_base:
        score += 90; razoes.append("fatura-documento")
    if b.fatura_numero and a.is_pagamento and a.pagamento_documento_base and b.fatura_numero == a.pagamento_documento_base:
        score += 90; razoes.append("fatura-documento")

    # 5) DPS pode aparecer como documento no recibo de alguns fornecedores.
    if a.dps_numero and b.is_pagamento and b.pagamento_documento_base and a.dps_numero == b.pagamento_documento_base:
        score += 75; razoes.append("dps-documento")
    if b.dps_numero and a.is_pagamento and a.pagamento_documento_base and b.dps_numero == a.pagamento_documento_base:
        score += 75; razoes.append("dps-documento")

    # Validadores complementares. Nao criam pareamento sozinhos com facilidade.
    if a.provider_cnpj and b.provider_cnpj and a.provider_cnpj == b.provider_cnpj:
        score += 12; razoes.append("fornecedor")
    if a.company_cnpj and b.company_cnpj and a.company_cnpj == b.company_cnpj:
        score += 12; razoes.append("empresa")
    if a.valor and b.valor and _mesmo_valor(a.valor, b.valor):
        score += 10; razoes.append("valor")
    if comp:
        score += 4

    return score, "+".join(razoes)


def _montar_componentes(docs: list[DocumentoInfo]) -> list[list[DocumentoInfo]]:
    """Cria pares/grupos por evidencias documentais, nunca por nome de arquivo."""
    n = len(docs)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Primeiro usa somente relacoes fortes (>= 80). Isso cobre NF, RPS e Fatura.
    fortes: list[tuple[int, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            score, _ = _score_pareamento(docs[i], docs[j])
            if score >= 80:
                fortes.append((score, i, j))
    for _score, i, j in sorted(fortes, reverse=True):
        union(i, j)

    # Fallback: fornecedor + empresa + valor + papeis complementares, apenas quando
    # existe um unico candidato. Evita juntar notas distintas do mesmo fornecedor.
    for i, doc in enumerate(docs):
        if len([x for x in range(n) if find(x) == find(i)]) > 1:
            continue
        candidatos: list[tuple[int, int]] = []
        for j, other in enumerate(docs):
            if i == j or find(i) == find(j):
                continue
            score, _ = _score_pareamento(doc, other)
            if score >= 34 and _complementares(doc, other):
                candidatos.append((score, j))
        candidatos.sort(reverse=True)
        if candidatos and (len(candidatos) == 1 or candidatos[0][0] > candidatos[1][0]):
            union(i, candidatos[0][1])

    comps: dict[int, list[DocumentoInfo]] = {}
    for i, doc in enumerate(docs):
        comps.setdefault(find(i), []).append(doc)
    return list(comps.values())


def _montar_grupo(key: str, docs: list[DocumentoInfo]) -> GrupoLancamento:
    numero = _numero_grupo(docs)
    tipo_votes: dict[str, int] = {}
    for d in docs:
        tipo_votes[d.tipo_hint] = tipo_votes.get(d.tipo_hint, 0) + max(1, d.score_nota + d.score_pagamento)
    tipo = max(tipo_votes, key=tipo_votes.get) if tipo_votes else "nfse"

    nota_doc = max(docs, key=lambda d: (d.score_nota - d.score_pagamento, d.score_nota))
    pagamento_doc = max(docs, key=lambda d: (d.score_pagamento - d.score_nota, d.score_pagamento))
    if len(docs) == 1:
        nota_doc = pagamento_doc = docs[0]

    grupo = GrupoLancamento(
        key=key,
        numero=numero,
        documentos=list(docs),
        nota_pdf=nota_doc.path,
        pagamento_pdf=pagamento_doc.path,
        conferencia_pdf=pagamento_doc.path if pagamento_doc else nota_doc.path,
        tipo_sugerido=tipo,
    )

    try:
        dados, _nf, _pg = extrair_dados(grupo.nota_pdf, grupo.pagamento_pdf)
        grupo.dados = dados
        if numero:
            # O agrupador conhece melhor a referencia fiscal quando o boleto usa RPS.
            grupo.dados.numero = numero
        elif grupo.dados.numero:
            grupo.numero = grupo.dados.numero
    except Exception as exc:
        grupo.avisos.append(f"Leitura parcial: {exc}")

    if len(docs) == 1:
        grupo.avisos.append("Apenas 1 PDF relacionado a este lançamento.")
    else:
        tem_nota = any(d.score_nota > 0 for d in docs)
        tem_pag = any(d.score_pagamento > 0 for d in docs)
        if not tem_nota:
            grupo.avisos.append("Nenhuma nota fiscal claramente identificada; será usado o documento disponível.")
        if not tem_pag:
            grupo.avisos.append("Nenhum boleto/recibo claramente identificado; a nota será aberta para conferência.")

    if not grupo.numero:
        grupo.avisos.append("Número/referência do documento não identificado; o documento foi mantido como lançamento independente.")

    if grupo.dados:
        faltantes = []
        for label, value in {
            "número/referência": grupo.dados.numero,
            "valor": grupo.dados.valor,
            "emissão": grupo.dados.emissao,
            "CNPJ fornecedor": grupo.dados.provider_cnpj,
            "empresa": grupo.dados.company_id,
        }.items():
            if not value:
                faltantes.append(label)
        if faltantes:
            grupo.avisos.append("Dados não identificados: " + ", ".join(faltantes) + ".")
    return grupo


def agrupar_documentos(paths: list[str | Path]) -> list[GrupoLancamento]:
    unicos: list[Path] = []
    for raw in paths:
        p = Path(raw).resolve()
        if p.suffix.lower() == ".pdf" and p.exists() and p not in unicos:
            unicos.append(p)
    if not unicos:
        return []

    docs = [analisar_documento(p) for p in unicos]
    componentes = _montar_componentes(docs)
    result = [_montar_grupo(f"GRUPO-{idx:04d}", comp) for idx, comp in enumerate(componentes, start=1)]
    result.sort(key=lambda g: (g.numero == "", g.numero or g.key))
    return result
