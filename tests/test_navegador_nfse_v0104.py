"""Local browser regression; every request is intercepted, no real Agilize access.
AGILIZE_TEST_BROWSER can specify a browser. Uses Chromium on Linux or Edge on Windows.
"""
from pathlib import Path
import os
import shutil
import sys
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from playwright.sync_api import sync_playwright
import agilize as a
from models import NotaDados

HTML = r'''<!doctype html><meta charset="utf-8"><title>Local fixture</title>
<button onclick="window.newCount++">Enviar Nota</button>
<select id="searchType"><option value="number">Numero</option><option value="cnpj">Documento fornecedor</option><option value="all">Pesquisar tudo</option></select>
<select id="status"><option value="9999">Todos os status</option><option value="99">Efetuada</option></select>
<select id="underline_select"><option value="0">Todas as empresas</option><option value="8">LCR COMERCIO DE MOVEIS LTDA (0001-49)</option></select>
<input id="dateStart" type="date" wire:model.debounce.1000ms="filter.dateStart" value="2026-09-29">
<input id="dateEnd" type="date" wire:model.debounce.1000ms="filter.dateEnd" value="2026-09-29">
<input id="searchInput"><table><tbody></tbody></table>
<div id="modal-container" style="display:none"></div>
<script>
const $ = id => document.getElementById(id);
window.newCount=0; window.openedNumber=''; window.resetCount=1;
const rows=[{num:'2657',issued:'2026-08-21',date:'21/08/2026',status:'Efetuada'},
{num:'2600000002721',issued:'2026-09-21',date:'21/09/2026',status:'Nao possui'}];
function render(){
 const q=$('searchInput').value, kind=$('searchType').value;
 document.querySelector('tbody').innerHTML='';
 for(const row of rows){
  if(row.issued < $('dateStart').value || row.issued > $('dateEnd').value) continue;
  if($('status').value==='99' && row.status!=='Efetuada') continue;
  if(kind==='number' && q!==row.num) continue;
  if(kind==='cnpj') continue; // Force name fallback, as reported.
  if(kind==='all' && q!=='STARTING HUB DE INOVACAO LTDA') continue;
  const tr=document.createElement('tr');
  const cells=['',row.num,'R$ 1.621,00',row.date,'LCR COMERCIO DE MOVEIS LTDA (0001-49)',
    '46.882.111/0001-70','STARTING HUB DE INOVACAO LTDA','',row.status,'','',''];
  for(const value of cells){const td=document.createElement('td');td.textContent=value;tr.append(td);}
  const button=document.createElement('button');button.textContent='Ver nota';
  button.onclick=()=>{window.openedNumber=row.num;$('modal-container').style.display='block';
   $('modal-container').innerHTML='<h2>Enviar nota importada (NFS-E)</h2><textarea id="observacao"></textarea>';};
  tr.lastChild.append(button);document.querySelector('tbody').append(tr);
 }
}
for(const id of ['searchType','status','underline_select','searchInput']){
 $(id).addEventListener(id==='searchInput'?'input':'change',()=>setTimeout(()=>{
  $('dateStart').value='2026-09-29';$('dateEnd').value='2026-09-29';render();},75));
}
for(const id of ['dateStart','dateEnd']){
 $(id).addEventListener('input',()=>setTimeout(()=>{
  if(window.resetCount>0){window.resetCount--;$('dateStart').value='2026-09-29';}render();},90));
}
render();
</script>'''


def main():
    executable=os.environ.get('AGILIZE_TEST_BROWSER') or shutil.which('chromium')
    args=dict(headless=True)
    if executable: args['executable_path']=executable
    elif os.name=='nt': args['channel']='msedge'
    d=NotaDados(numero='2721',valor='1.621,00',emissao='2026-09-21',company_id=8,
        company_name='LCR COMERCIO DE MOVEIS LTDA (0001-49)',company_cnpj='09.081.947/0001-49',
        provider_cnpj='46.882.111/0001-70',provider_name='STARTING HUB DE INOVACAO LTDA')
    with sync_playwright() as p:
        browser=p.chromium.launch(**args)
        try:
            page=browser.new_page()
            page.route('**/*',lambda route:route.fulfill(status=200,content_type='text/html',body=HTML))
            page.set_content(HTML);url=page.url
            with patch.object(a,'AGILIZE_URL',url):
                record=a._localizar_importada_prefixada_por_fornecedor(page,d,print,estrito=True)
                assert record['numero_cadastrado']=='2600000002721'
                assert page.locator('#dateStart').input_value()=='2026-06-01'
                assert page.locator('#dateEnd').input_value()=='2026-09-30'
                assert page.locator('#searchType').input_value()=='all'
                assert page.locator('#searchInput').input_value()==d.provider_name
                with patch.object(a,'_localizar_registro_existente',return_value=record):
                    result=a._buscar_e_abrir_importada_atual(page,d,print)
                assert result['existe'] and result['aberto']
                assert page.evaluate('window.openedNumber')=='2600000002721'
                assert page.evaluate('window.newCount')==0
            print('[OK] Browser local: dates reapplied after rerender; name search and imported modal, no new form.')
        finally:
            browser.close()

if __name__=='__main__': main()
