from __future__ import annotations

from dataclasses import dataclass

from config import AGILIZE_BASE_URL


@dataclass(frozen=True)
class TipoAgilize:
    key: str
    label: str
    path: str
    create_supported: bool = False

    @property
    def url(self) -> str:
        return AGILIZE_BASE_URL + self.path


TIPOS: dict[str, TipoAgilize] = {
    "nfe": TipoAgilize("nfe", "Notas NF-e/CT-e (DANFE)", "/notas", False),
    "nfse": TipoAgilize("nfse", "Notas NFS-E", "/nfs", True),
    "documentos": TipoAgilize("documentos", "Doc. - Contas a pagar", "/documentos", False),
}

ORDEM_PESQUISA = ("nfse", "documentos")


def ordem_pesquisa(preferido: str = "auto", sugerido: str = "nfse") -> list[TipoAgilize]:
    """Retorna somente as areas usadas para pesquisa de historico.

    NF-e/CT-e (DANFE) continua mapeado como tipo de documento para futuras
    evolucoes, mas nao participa da pesquisa de CNPJ/rateio.
    """
    primeiro = sugerido if preferido == "auto" else preferido

    # Contas a pagar usa uma semantica de pesquisa diferente da NFS-E.
    # Quando o destino escolhido/detectado e "documentos", nao caimos em NFS-E
    # como fallback: isso evita trocar a busca pelo nome do fornecedor por uma
    # busca de CNPJ e evita reutilizar uma referencia de outra area por engano.
    if primeiro == "documentos":
        return [TIPOS["documentos"]]

    keys: list[str] = []
    if primeiro in ORDEM_PESQUISA:
        keys.append(primeiro)
    for key in ORDEM_PESQUISA:
        if key not in keys:
            keys.append(key)
    return [TIPOS[key] for key in keys]


def label_tipo(key: str) -> str:
    if key == "auto":
        return "Automático"
    tipo = TIPOS.get(key)
    return tipo.label if tipo else key
