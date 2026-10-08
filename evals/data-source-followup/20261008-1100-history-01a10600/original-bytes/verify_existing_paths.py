"""Execute existing document HTTP and research HTTP/stdio-MCP paths without a model."""
import argparse
import asyncio
import json
import os
import socket
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=args.input;out=args.output;out.mkdir(parents=True,exist_ok=True)
assert not (out/'result.json').exists()
os.environ['PYTHONPATH']=str(root/'reused-libs')+os.pathsep+os.environ['PYTHONPATH']
sys.path.insert(0,str(root/'reused-libs'))
from fastapi import FastAPI
import httpx
import pypdf
import uvicorn
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from lgax_api.research_planning import ResearchWorkspace
from lgax_api.workspace_auth import TokenRegistry
from lgax_api.workspace_server import create_workspace_app, _load_document_store
from lgax_contracts import validate
from lgax_core.documents import DocumentRepository
from lgax_core.documents_server import create_app
from lgax_core.errors import DomainError

def digest(raw):return sha256(raw).hexdigest()
def objdigest(value):return digest(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
manifest=json.loads((root/'stage-manifest.json').read_text('utf-8'))
report={'record_id':manifest['record_id'],'checked_at_kst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
 'code_and_canonical_data_commit':manifest['fixed_code_and_canonical_data_commit'],'latest_main':manifest['latest_main_commit'],
 'pypdf_version':pypdf.__version__,'new_model_calls':0,'model_adapter_configured':False,'new_installs':0,'production_server_changed':False,
 'requests':[],'checks':[],'mcp_calls':[],'document_plan_kind':'reconstructed from existing canonical21+origins, no new feature judgement',
 'synthetic_or_independent_evaluation_inputs_used':False}
def save():
 (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
def check(name,okay,**data):
 report['checks'].append({'name':name,'passed':bool(okay),**data});save()
 if not okay:raise AssertionError(name)
def request(client,method,path,**kwargs):
 response=client.request(method,path,**kwargs)
 body=response.json() if response.headers.get('content-type','').startswith('application/json') else None
 input_raw=kwargs.get('content')
 if input_raw is None and 'json' in kwargs:input_raw=json.dumps(kwargs['json'],ensure_ascii=False).encode()
 report['requests'].append({'method':method,'path':path,'status':response.status_code,
  'input_sha256':digest(input_raw) if isinstance(input_raw,bytes) else None,'input_bytes':len(input_raw) if isinstance(input_raw,bytes) else None,
  'output_sha256':digest(response.content),'output_bytes':len(response.content),
  'error_code':body.get('error',{}).get('code') if isinstance(body,dict) else None})
 return response,body
@contextmanager
def server(app):
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 instance=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False))
 thread=threading.Thread(target=instance.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
 try:
  for _ in range(200):
   if instance.started:break
   if not thread.is_alive():raise RuntimeError('isolated server stopped during startup')
   time.sleep(.025)
  else:raise RuntimeError('isolated server did not start')
  yield f'http://127.0.0.1:{port}'
 finally:
  instance.should_exit=True;thread.join(10);sock.close()
  assert not thread.is_alive(),'owned isolated server did not stop'

packbase=root/'data/research/r8-public-research-20261007/d1-d2-01a10600/agent-input'
dataset_path=packbase/'canonical-models.dataset.json'
dataset=json.loads(dataset_path.read_text('utf-8'))
origins={row['evidence_id']:row for row in json.loads((root/'data/research/PM-DATA-intake-20261006/generated/origins.json').read_text('utf-8'))}
plan={'artifact_kind':'trusted_document_plan','dataset_version':dataset['dataset_version'],'documents':[]}
pdfs={}
for product in dataset['products']:
 model=product['model_id'];evidence=[x for x in dataset['evidence'] if x['model_id']==model]
 assert evidence and len({e['source_id'] for e in evidence})==1
 origin=origins[evidence[0]['id']]
 candidates=list((root/'data/sources/lg-manuals-20261005').glob(model+'-*.pdf'))
 assert len(candidates)==1 and digest(candidates[0].read_bytes())==origin['sha256']
 pdfs[model]=candidates[0]
 plan['documents'].append({'document_id':evidence[0]['source_id'],'product':deepcopy(product),
  'document_version':product['document_version'],'source_kind':'public','sha256':origin['sha256'],
  'url':origin['url'],'checked_at':origin['checked_at'],
  'features':[deepcopy(x) for x in dataset['features'] if x['model_id']==model],
  'selections':[{'evidence_id':e['id'],'page':e['locator']['page'],'section':e['locator']['section'],
    'excerpt':e['text'],'feature_ids':deepcopy(e['feature_ids'])} for e in evidence]})
(out/'document-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf-8')
report['document_plan_sha256']=digest((out/'document-plan.json').read_bytes())
token=__import__('secrets').token_urlsafe(48)
docdir=out/'isolated-registration';repo=DocumentRepository(docdir,plan,sys.executable)
headers={'Authorization':'Bearer '+token}
document_records={}
with server(create_app(repo,token)) as base,httpx.Client(base_url=base,headers=headers,timeout=90,trust_env=False) as client:
 for spec in sorted(plan['documents'],key=lambda s:['T876MEE1H1','DUE6BGL2E','MW23FDI'].index(s['product']['model_id'])):
  model=spec['product']['model_id'];did=spec['document_id'];raw=pdfs[model].read_bytes()
  response,body=request(client,'POST','/api/documents/'+did,content=raw)
  check(model+'_upload_parse_validate_http',response.status_code==200 and body.get('ok') is True,status=response.status_code,error=body.get('error'))
  record=body['data'];document_records[model]=record
  check(model+'_actual_text_extraction',record['parser']=='pypdf' and record['parser_version']==pypdf.__version__ and record['ocr_used'] is False,page_count=record['page_count'])
  response,body=request(client,'GET','/api/documents/'+did)
  check(model+'_saved_metadata',response.status_code==200 and body['data']==record)
  response,_=request(client,'GET','/api/documents/'+did+'/original')
  check(model+'_pdf_original_hash',response.status_code==200 and digest(response.content)==spec['sha256'])
  check(model+'_same_canonical_evidence',record['dataset']['evidence']==[e for e in dataset['evidence'] if e['model_id']==model],evidence_count=len(record['dataset']['evidence']))
  for evidence in record['dataset']['evidence']:
   response,body=request(client,'GET','/api/evidence/'+evidence['id'])
   check(evidence['id']+'_http_exact_scope',response.status_code==200 and body['data']['evidence']==evidence,
    model=model,source_id=evidence['source_id'],version=evidence['document_version'],source_kind=evidence['source_kind'],locator=evidence['locator'])
  term={'T876MEE1H1':'선반','DUE6BGL2E':'바구니','MW23FDI':'출력'}[model]
  response,body=request(client,'GET','/api/evidence/search',params={'q':term,'model_id':model,'document_version':spec['document_version']})
  validate('EvidenceSearchResponse',body)
  check(model+'_scoped_search',response.status_code==200 and body['data']['total']>0 and all(e['model_id']==model and e['document_version']==spec['document_version'] for e in body['data']['items']),total=body['data']['total'])
  wrong=raw[:-1]+bytes([raw[-1]^1])
  response,body=request(client,'POST','/api/documents/'+did,content=wrong)
  check(model+'_changed_pdf_rejected',response.status_code==400 and body['error']['code']=='SOURCE_MISMATCH')
  response,body=request(client,'POST','/api/documents/'+did,content=raw)
  check(model+'_same_pdf_idempotent',response.status_code==200 and body['data']['idempotent'] is True and body['data']['dataset']==record['dataset'])
report['task1']={'status':'PASS','real_document_http_uploads':3,'parsed_pages':sum(r['page_count'] for r in document_records.values()),'canonical_evidence_read':len(dataset['evidence']),'path':'existing lgax_core.documents_server → DocumentRepository._parse → pypdf → SQLite → evidence HTTP',
 'review_csv_upload_proved_in_this_run':False,'new_research_bundle_registration_is_operator_json_load':True}
save()

bundle_paths=[packbase/group/'research-bundle.json' for group in ['fridge','dishwasher','microwave']]
expected={json.loads(p.read_text('utf-8'))['bundle_id']:json.loads(p.read_text('utf-8')) for p in bundle_paths}
registry=TokenRegistry([{'principal_id':'isolated-data-reader','role':'editor','token_sha256':digest(token.encode())}])
research=ResearchWorkspace(out/'isolated-workspace.research.sqlite3',bundle_paths,planner=None)
evidence_store=_load_document_store(dataset_path,digest(dataset_path.read_bytes()))
def app_for(ws):return create_workspace_app(out/'isolated-workspace.sqlite3',registry,evidence_store=evidence_store,research_workspace=ws)
async def read_stdio(base,label):
 credential=out/('ephemeral-'+label+'.json');credential.write_text(json.dumps({'token':token}),'utf-8')
 try:
  params=StdioServerParameters(command=sys.executable,args=['-B','-m','lgax_mcp.workspace_server','--url',base,'--credential-file',str(credential)],env=dict(os.environ),cwd=str(root))
  async with stdio_client(params) as (read,write),ClientSession(read,write) as session:
   await session.initialize()
   listed=await session.call_tool('list_research_bundles',{})
   def body(result):
    if result.structuredContent is not None:return result.structuredContent
    return json.loads(next(x.text for x in result.content if x.type=='text'))
   check('mcp_'+label+'_list_counts',len(body(listed)['bundles'])==3)
   for bundle_id,bundle in expected.items():
    result=await session.call_tool('get_research_bundle',{'bundle_id':bundle_id});readback=body(result)
    check('mcp_'+label+'_'+bundle['product_group']+'_same184_sources',not result.isError and readback==bundle,sources=len(bundle['sources']))
    report['mcp_calls'].append({'phase':label,'tool':'get_research_bundle','bundle_id':bundle_id,'structured_result_sha256':objdigest(readback),'success':True})
 finally:credential.unlink(missing_ok=True)

with server(app_for(research)) as base,httpx.Client(base_url=base,headers=headers,timeout=20,trust_env=False) as client:
 response,body=request(client,'GET','/api/research/bundles')
 check('research_operator_load_and_http_list',response.status_code==200 and len(body['bundles'])==3 and sum(v['source_count'] for v in body['bundles'])==184)
 for bundle_id,bundle in expected.items():
  response,body=request(client,'GET','/api/research/bundles/'+bundle_id)
  check(bundle['product_group']+'_http_original_sources_and_metadata',response.status_code==200 and body==bundle,sources=len(bundle['sources']),reviews=sum(s['source_type']=='review' for s in bundle['sources']))
  altered=deepcopy(body);altered['sources'][0].update(text='ISOLATED RESPONSE MUTATION',page_model='other-model',document_version='changed-version',source_kind='synthetic')
  check(bundle['product_group']+'_response_mutation_cannot_change_server',research.get_bundle(bundle_id)==bundle)
  response,_=request(client,'PATCH','/api/research/bundles/'+bundle_id,json=altered)
  check(bundle['product_group']+'_no_bundle_overwrite_route',response.status_code==405 and research.get_bundle(bundle_id)==bundle)
 response,body=request(client,'GET','/api/research/bundles/nonexistent-data-id')
 check('unknown_bundle_rejected',response.status_code==404 and body['error']['code']=='NOT_FOUND')
 response=client.get('/api/research/bundles',headers={'Authorization':'invalid'})
 check('research_missing_or_invalid_auth_rejected',response.status_code==401)
 response=client.get('/api/research/bundles',headers={'Origin':'https://unrelated.invalid'})
 check('research_foreign_origin_rejected',response.status_code==403)
 asyncio.run(read_stdio(base,'before-restart'))
 for bundle_id,bundle in expected.items():
  response,body=request(client,'POST','/api/research/planning-runs',json={'bundle_id':bundle_id,'goal':'ISOLATED TEST ONLY: generation must stay disabled','constraints':[]})
  check(bundle['product_group']+'_disabled_generation_no_fake_result',response.status_code==501 and body['error']['code']=='NOT_IMPLEMENTED')
report['task2']={'status':'PASS','http_source_objects':184,'development_review_objects':141,'mcp_transport':'actual stdio initialize/call_tool → existing WorkspaceClient → actual container loopback HTTP',
 'registered_in_operating_server':False,'real_ai_generated':False,'generation_disabled_response':{'http':501,'code':'NOT_IMPLEMENTED'},'input_hashes':{p.parent.name:digest(p.read_bytes()) for p in bundle_paths}}
save()

reopened=DocumentRepository(docdir,plan,sys.executable)
with server(create_app(reopened,token)) as base,httpx.Client(base_url=base,headers=headers,timeout=20,trust_env=False) as client:
 for model,record in document_records.items():
  response,body=request(client,'GET','/api/documents/'+record['document_id'])
  check(model+'_sqlite_reopen_same_metadata',response.status_code==200 and body['data']==record)
  for evidence in record['dataset']['evidence']:
   response,body=request(client,'GET','/api/evidence/'+evidence['id'])
   check(evidence['id']+'_reopen_same_original_scope',response.status_code==200 and body['data']['evidence']==evidence)
for model,record in document_records.items():
 original=deepcopy(record)
 for field,bad in [('model_id','wrong-model'),('document_version','wrong-version'),('source_id','wrong-source'),('source_kind','synthetic')]:
  altered=deepcopy(original);altered['dataset']['evidence'][0][field]=bad
  with sqlite3.connect(reopened.db) as conn:conn.execute('UPDATE documents SET record=? WHERE id=?',(json.dumps(altered,ensure_ascii=False),record['document_id']))
  observed=None
  try:reopened.store()
  except DomainError as error:observed=error.code
  finally:
   with sqlite3.connect(reopened.db) as conn:conn.execute('UPDATE documents SET record=? WHERE id=?',(json.dumps(original,ensure_ascii=False),record['document_id']))
  check(model+'_isolated_sqlite_'+field+'_tamper_rejected',observed=='SOURCE_MISMATCH')
new_research=ResearchWorkspace(out/'isolated-workspace.research.sqlite3',bundle_paths,planner=None)
with server(app_for(new_research)) as base,httpx.Client(base_url=base,headers=headers,timeout=20,trust_env=False) as client:
 for bundle_id,bundle in expected.items():
  response,body=request(client,'GET','/api/research/bundles/'+bundle_id)
  check(bundle['product_group']+'_reloaded_same_sources_and_hash',response.status_code==200 and body==bundle and new_research.digests[bundle_id]==research.digests[bundle_id])
 asyncio.run(read_stdio(base,'after-restart'))
with sqlite3.connect(new_research.db_path) as conn:
 runs=conn.execute('SELECT COUNT(*) FROM research_runs').fetchone()[0]
 attempts=conn.execute('SELECT COUNT(*) FROM research_attempts').fetchone()[0]
check('disabled_generation_creates_no_run_or_attempt',runs==0 and attempts==0,runs=runs,attempts=attempts)
source_drift=[path for path,sha in manifest['source_hashes'].items() if digest((root/path).read_bytes())!=sha]
check('all_fixed_input_source_bytes_preserved',not source_drift,checked_files=len(manifest['source_hashes']))
with sqlite3.connect(reopened.db) as conn:
 document_count=conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
 integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
check('document_sqlite_integrity',document_count==3 and integrity=='ok',documents=document_count,integrity=integrity)
report['task3']={'status':'PASS','document_sqlite_reopen_and_provenance_preserved':True,'tampered_isolated_records_rejected':12,
 'research_sources_reloaded_from_same_operator_files':True,'research_sources_persisted_in_sqlite':False,
 'actual_model_result_sqlite_resumption_tested':False,'saved_generated_runs':runs,'model_attempts':attempts,
 'process_note':'Fresh existing service instances and a restarted stdio child in the same zero-auth container; not operating service restart',
 'remaining_inputs':['PM approval and merge/integration','CORE/PM fixed actual planning outputs + raw/usage + same HTTP/MCP run','D4 actual producer audit','Exact purchased SKUs/review posting dates/shared-SKU applicability','Independent reviewer/gold/private handoff']}
report['result']='PASS';report['passed_checks']=sum(x['passed'] for x in report['checks']);save()
print(json.dumps({'result':'PASS','checks':report['passed_checks'],'documents':3,'parsed_pages':report['task1']['parsed_pages'],'evidence':21,'research_sources':184,'reviews':141,'new_model_calls':0,'operating_changes':0},ensure_ascii=False))
