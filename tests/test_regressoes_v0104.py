"""Regression tests for the real 2721 case; no production/network writes."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import agilize as a
import agilize_batch as b
from models import NotaDados


def dados():
    return NotaDados(
        numero='2721', valor='1.621,00', emissao='2026-09-21',
        company_id=8, company_name='LCR COMERCIO DE MOVEIS LTDA (0001-49)',
        company_cnpj='09.081.947/0001-49', provider_cnpj='46.882.111/0001-70',
        provider_name='STARTING HUB DE INOVACAO LTDA', vencimento='2026-10-05',
    )


def cells(numero='2600000002721', status='Nao possui'):
    d = dados()
    return ['', numero, d.valor, '21/09/2026', d.company_name, d.provider_cnpj,
            d.provider_name, '', status, '', '', 'Ver nota']


def registro(status='Nao possui'):
    return dict(idx=0, cells=cells(status=status), situacao=status,
                numero_cadastrado='2600000002721', match_prefixado=True, estrito=True)


class Campo:
    def __init__(self, value):
        self.value = value
        self.fills = []
    def input_value(self):
        return self.value
    def fill(self, value):
        self.value = value
        self.fills.append(value)
    def press(self, key):
        assert key == 'Tab'


class Regressoes0104(unittest.TestCase):
    def test_janela_inclui_atual_e_tres_anteriores(self):
        self.assertEqual(a._periodo_busca_importada_por_fornecedor('2026-09-21'),
                         ('2026-06-01', '2026-09-30'))
        self.assertEqual(a._periodo_busca_importada_por_fornecedor('2027-01-31'),
                         ('2026-10-01', '2027-01-31'))

    def test_minimo_dois_meses_mesmo_parametro_menor(self):
        self.assertEqual(a._periodo_busca_importada_por_fornecedor('2026-09-21', 1),
                         ('2026-07-01', '2026-09-30'))

    def test_ano_bissexto(self):
        self.assertEqual(a._periodo_busca_importada_por_fornecedor('2028-02-29'),
                         ('2027-11-01', '2028-02-29'))

    def test_2721_prefixada_confirma_identidade_completa(self):
        self.assertTrue(a._linha_atual_confirmada(cells(), dados()))
        self.assertTrue(a._linha_atual_confirmada(cells(numero='002721'), dados()))
        self.assertFalse(a._linha_atual_confirmada(cells(numero='2657'), dados()))
        self.assertFalse(a._linha_atual_confirmada(cells(numero='12721'), dados()))

    def test_nao_confunde_filial_fornecedor_valor_emissao(self):
        for index, value in [(4, 'LCR COMERCIO DE MOVEIS LTDA (0008-15)'),
                             (5, '00.000.000/0001-00'), (2, '1.620,00'),
                             (3, '20/09/2026')]:
            with self.subTest(index=index):
                row = cells(); row[index] = value
                self.assertFalse(a._linha_atual_confirmada(row, dados()))

    def test_campos_insuficientes_nao_autorizam_redirecionar(self):
        for field in ['company_name', 'provider_cnpj', 'valor', 'emissao']:
            d = dados(); setattr(d, field, '')
            if field == 'company_name':
                d.company_cnpj = ''
            with self.subTest(field=field):
                self.assertFalse(a._linha_atual_confirmada(cells(), d))

    def test_datas_reaplicadas_apos_um_rerender(self):
        start, end = Campo('2026-09-29'), Campo('2026-09-29')
        waits = 0
        def settle(*args, **kwargs):
            nonlocal waits
            waits += 1
            if waits == 1:
                start.value = '2026-09-29'
        logs = []
        with patch.object(a, '_campos_periodo_lista', return_value=(start, end)), \
             patch.object(a, '_aguardar_pesquisa_livewire', side_effect=settle):
            a._aplicar_periodo_lista(object(), '2026-06-01', '2026-09-30', logs.append)
        self.assertEqual(start.value, '2026-06-01')
        self.assertEqual(end.value, '2026-09-30')
        self.assertEqual(waits, 2)
        self.assertTrue(any('datas confirmadas na tela' in m for m in logs))

    def test_datas_que_nao_permanecem_interrompem(self):
        start, end = Campo('2026-09-29'), Campo('2026-09-29')
        def reset(*args, **kwargs):
            start.value = '2026-09-29'
        with patch.object(a, '_campos_periodo_lista', return_value=(start, end)), \
             patch.object(a, '_aguardar_pesquisa_livewire', side_effect=reset) as wait:
            with self.assertRaisesRegex(RuntimeError, 'nenhum novo lancamento'):
                a._aplicar_periodo_lista(object(), '2026-06-01', '2026-09-30')
        self.assertEqual(wait.call_count, 3)

    def test_campos_ausentes_interrompem(self):
        with patch.object(a, '_campos_periodo_lista', side_effect=RuntimeError('ausentes')):
            with self.assertRaisesRegex(RuntimeError, 'Pesquisa inconclusiva'):
                a._aplicar_periodo_lista(object(), '2026-06-01', '2026-09-30')

    def test_intervalo_invertido_nao_escreve_na_tela(self):
        with patch.object(a, '_campos_periodo_lista') as get:
            with self.assertRaises(ValueError):
                a._aplicar_periodo_lista(object(), '2026-10-01', '2026-09-30')
            get.assert_not_called()

    def test_busca_nome_nao_seleciona_documento_fornecedor(self):
        page = MagicMock()
        select = page.locator.return_value
        select.count.return_value = 1
        select.first.is_visible.return_value = True
        opts = select.first.locator.return_value
        labels = [('Documento fornecedor', 'cnpj'), ('Pesquisar tudo', 'all')]
        options = []
        for label, val in labels:
            opt = MagicMock()
            opt.inner_text.return_value = label
            opt.get_attribute.return_value = val
            options.append(opt)
        opts.count.return_value = len(options)
        opts.nth.side_effect = lambda i: options[i]
        with patch.object(a, '_aguardar_livewire'):
            self.assertTrue(a._selecionar_tipo_pesquisa(page, ('Nome fornecedor', 'Fornecedor', 'Pesquisar tudo', 'Tudo')))
        select.first.select_option.assert_called_once_with('all')

    def test_texto_resetado_interrompe(self):
        page = MagicMock()
        page.locator.return_value.input_value.return_value = 'outro texto'
        with patch.object(a, '_aguardar_livewire'), patch.object(a, '_aplicar_periodo_lista'):
            with self.assertRaisesRegex(RuntimeError, 'texto de pesquisa'):
                a._pesquisar_lista_com_periodo(page, '2721', '2026-06-01', '2026-09-30')

    def setup_session(self, stack):
        stack.enter_context(patch.object(b, 'resolver_navegador', return_value=MagicMock()))
        session = b.AgilizeSession(logger=lambda msg: None)
        session.context = MagicMock()
        session.open = MagicMock()
        session._aguardar_capacidade = MagicMock()
        session._nova_pagina = MagicMock(return_value=MagicMock())
        session._ensure_login = MagicMock()
        return session

    def test_documentos_reutiliza_nfse_prefixada_sem_formulario_novo(self):
        with ExitStack() as stack:
            session = self.setup_session(stack)
            lookup = stack.enter_context(patch.object(b, '_localizar_registro_existente', return_value=registro()))
            history = stack.enter_context(patch.object(b, 'buscar_referencia_multitipo', return_value=None))
            nfse = stack.enter_context(patch.object(b, '_preencher_destino', return_value='importado'))
            docs = stack.enter_context(patch.object(b, '_preencher_destino_documentos'))
            result = session.preparar_lancamento(dados(), ['nota.pdf', 'boleto.pdf'], '', 'documentos', 'documentos')
            self.assertEqual(result['state'], 'aberto')
            self.assertTrue(lookup.call_args.kwargs['estrito'])
            self.assertEqual(history.call_args.args[2:4], ('nfse', 'nfse'))
            self.assertEqual(nfse.call_args.kwargs['precheck']['numero_cadastrado'], '2600000002721')
            docs.assert_not_called()

    def test_sem_pre_cadastro_preserva_destino_documentos(self):
        with ExitStack() as stack:
            session = self.setup_session(stack)
            stack.enter_context(patch.object(b, '_localizar_registro_existente', return_value=None))
            stack.enter_context(patch.object(b, 'buscar_referencia_multitipo', return_value=None))
            nfse = stack.enter_context(patch.object(b, '_preencher_destino'))
            docs = stack.enter_context(patch.object(b, '_preencher_destino_documentos', return_value='documento_novo'))
            session.preparar_lancamento(dados(), ['nota.pdf'], '', 'documentos', 'documentos')
            nfse.assert_not_called(); docs.assert_called_once()

    def test_resultado_vazio_nao_bloqueia_pesquisas_seguintes(self):
        with ExitStack() as stack:
            session = self.setup_session(stack)
            lookup = stack.enter_context(patch.object(b, '_localizar_registro_existente', return_value=None))
            history = stack.enter_context(patch.object(b, 'buscar_referencia_multitipo', return_value=None))
            stack.enter_context(patch.object(b, '_preencher_destino_documentos', return_value='documento_novo'))
            for _ in range(3):
                session.preparar_lancamento(dados(), ['nota.pdf'], '', 'documentos', 'documentos')
            self.assertEqual(lookup.call_count, 3)
            self.assertEqual(history.call_count, 3)
            self.assertEqual(session._historico_cache, {})

    def test_cache_positivo_nao_pula_precheck(self):
        with ExitStack() as stack:
            session = self.setup_session(stack)
            lookup = stack.enter_context(patch.object(b, '_localizar_registro_existente', return_value=registro()))
            history = stack.enter_context(patch.object(b, 'buscar_referencia_multitipo', return_value={
                'tipo': 'nfse', 'tipo_label': 'Notas NFS-E', 'numero': '2657', 'emissao': '2026-08-21',
                'observacao': '- DADOS PARA PAGAMENTO:\nBOLETO\n- ONDE FOI UTILIZADO ESTA COMPRA (RATEIO):\nLOJA',
            }))
            stack.enter_context(patch.object(b, '_preencher_destino', return_value='importado'))
            for _ in range(2):
                session.preparar_lancamento(dados(), ['nota.pdf'], '', 'documentos', 'documentos')
            self.assertEqual(lookup.call_count, 2)
            self.assertEqual(history.call_count, 1)

    def test_erro_precheck_nao_abre_formulario_nem_consulta_historico(self):
        with ExitStack() as stack:
            session = self.setup_session(stack)
            stack.enter_context(patch.object(b, '_localizar_registro_existente', side_effect=RuntimeError('Pesquisa inconclusiva')))
            history = stack.enter_context(patch.object(b, 'buscar_referencia_multitipo'))
            nfse = stack.enter_context(patch.object(b, '_preencher_destino'))
            docs = stack.enter_context(patch.object(b, '_preencher_destino_documentos'))
            with self.assertRaisesRegex(RuntimeError, 'inconclusiva'):
                session.preparar_lancamento(dados(), ['nota.pdf'], '', 'documentos', 'documentos')
            history.assert_not_called(); nfse.assert_not_called(); docs.assert_not_called()

    def test_ja_efetuada_pula_anexos_e_historico(self):
        with ExitStack() as stack:
            session = self.setup_session(stack)
            stack.enter_context(patch.object(b, '_localizar_registro_existente', return_value=registro('Efetuada')))
            history = stack.enter_context(patch.object(b, 'buscar_referencia_multitipo'))
            docs = stack.enter_context(patch.object(b, '_preencher_destino_documentos'))
            result = session.preparar_lancamento(dados(), ['nota.pdf'], '', 'documentos', 'documentos')
            self.assertEqual(result['state'], 'ja_processado')
            history.assert_not_called(); docs.assert_not_called()

    def test_pre_cadastro_desaparecido_nao_cria_novo(self):
        with patch.object(a, '_localizar_registro_existente', return_value=None), \
             patch.object(a, '_preencher_create') as create:
            with self.assertRaisesRegex(RuntimeError, 'desapareceu'):
                a._preencher_destino(MagicMock(), dados(), ['nota.pdf'], None, precheck=registro())
            create.assert_not_called()

    def test_status_mudou_no_recheck_nao_reprocessa(self):
        with patch.object(a, '_localizar_registro_existente', return_value=registro('Efetuada')), \
             patch.object(a, '_preencher_campos_complementares') as fill:
            result = a._preencher_destino(MagicMock(), dados(), ['nota.pdf'], None, precheck=registro())
            self.assertEqual(result, 'ja_processado')
            fill.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
