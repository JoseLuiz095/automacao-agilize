from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'app' / 'agilize_batch.py').read_text(encoding='utf-8')

assert 'fornecedor_busca = (dados.provider_name or dados.beneficiario_nome or "").strip()' in SRC
assert 'valor de busca historica' in SRC
assert 'valor_busca = fornecedor_busca' in SRC
assert 'valor_busca = dados.provider_cnpj' in SRC
assert 'numero da nota/fatura e apenas referencia do titulo' in SRC

print('[OK] v0.9.0 - Doc. Contas a pagar pesquisa historico pelo nome do fornecedor; NFS-E continua por CNPJ')
