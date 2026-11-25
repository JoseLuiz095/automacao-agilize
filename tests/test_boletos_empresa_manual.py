from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from batch import agrupar_documentos
from pdf_reader import _achar_vencimento_boleto


def criar_boleto(path, numero, nosso_numero, valor, emissao, vencimento):
    texto = f'''EMPRESA TESTE LTDA
46.882.111/0001-70
Recibo do Pagador
Beneficiário
EMPRESA TESTE LTDA
CPF/CNPJ Beneficiário
46.882.111/0001-70
Vencimento
{vencimento}
Pagador
LCR COM***** DE MOV*** LTD* / 09.***.***/****-05
Nº documento
{numero}
Nosso número
{nosso_numero}
(=) Valor Documento
R$ {valor}
Demonstrativo
(+) Prestação de serviços - R$ 20,00
Beneficiário
EMPRESA TESTE LTDA / CNPJ: 46.882.111/0001-70 / RUA TESTE
Data do documento
{emissao}
Nº documento
{numero}
Nosso número
{nosso_numero}
(=) Valor do Documento
R$ {valor}
Ficha de Compensação
'''
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((35, 35), texto, fontsize=9, lineheight=1.2)
    doc.save(str(path))
    doc.close()


class TestBoletos(unittest.TestCase):
    def test_dois_boletos_independentes_e_leitura_do_documento(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a.pdf', Path(temp) / 'b.pdf'
            criar_boleto(a, '1234567', '9876543-2', '102,02', '16/11/2026', '18/11/2026')
            criar_boleto(b, '1234568', '9876544-3', '172,57', '15/11/2026', '20/11/2026')
            grupos = agrupar_documentos([a, b])
            self.assertEqual(len(grupos), 2)
            dados = {g.numero: g.dados for g in grupos}
            self.assertEqual(set(dados), {'1234567', '1234568'})
            self.assertEqual(dados['1234567'].nosso_numero, '9876543-2')
            self.assertEqual(dados['1234567'].emissao, '2026-11-16')
            self.assertEqual(dados['1234567'].valor, '102,02')
            self.assertEqual(dados['1234568'].vencimento, '2026-11-20')
            self.assertEqual(dados['1234568'].provider_name, 'EMPRESA TESTE LTDA')
            self.assertIsNone(dados['1234567'].company_id)
            self.assertIsNone(dados['1234568'].company_id)

    def test_vencimento_rotulado_nao_e_substituido_por_data_posterior(self):
        texto = 'Recibo do Pagador\nVencimento\n18/11/2026\nData processamento\n21/11/2026\n'
        self.assertEqual(_achar_vencimento_boleto(texto), '2026-11-18')


if __name__ == '__main__':
    unittest.main()
