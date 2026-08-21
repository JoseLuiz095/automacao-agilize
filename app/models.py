from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class NotaDados:
    # Dados principais que serao enviados ao Agilize.
    numero: str = ""
    valor: str = ""
    emissao: str = ""          # yyyy-mm-dd
    provider_cnpj: str = ""
    provider_name: str = ""
    company_cnpj: str = ""
    company_id: Optional[int] = None
    company_name: str = ""
    vencimento: str = ""       # yyyy-mm-dd
    aprovador: str = ""
    observacao: str = ""

    # Dados da NFS-e usados para validacao interna e futuras evolucoes.
    competencia: str = ""
    chave_acesso_nfse: str = ""
    numero_dps: str = ""
    serie_dps: str = ""
    codigo_tributacao: str = ""
    codigo_nbs: str = ""
    descricao_servico: str = ""

    # Dados do documento de pagamento/boleto.
    pagamento_tipo: str = ""
    pagamento_meio_descricao: str = ""
    referencia_periodo: str = ""
    pagamento_valor: str = ""
    pagamento_emissao: str = ""
    pagamento_numero_documento: str = ""
    banco: str = ""
    banco_codigo: str = ""
    linha_digitavel: str = ""
    nosso_numero: str = ""
    beneficiario_nome: str = ""
    beneficiario_cnpj: str = ""
    pix_chave: str = ""

    # Referencia recuperada no Agilize.
    nota_base_numero: str = ""
    nota_base_emissao: str = ""

    def to_dict(self):
        return asdict(self)
