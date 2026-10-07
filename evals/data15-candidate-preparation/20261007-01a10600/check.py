"""Metadata only: validate private candidate input shape and exposure separation."""
import argparse
from hashlib import sha256
from pathlib import Path
import json
import re
import unicodedata
from jsonschema import Draft202012Validator
def load(p):return json.loads(p.read_bytes())
def canonical(value):return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
def normalized(text):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip()
def walk(value):
    if isinstance(value,dict):
        yield value
        for x in value.values():yield from walk(x)
    elif isinstance(value,list):
        for x in value:yield from walk(x)
def main():
    cli=argparse.ArgumentParser();cli.add_argument('--input',type=Path,required=True);cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args();root,out=args.input,args.output
    meta=load(root/'metadata.json');schema=load(root/'schema.json')
    refs=[(r,load(root/r['staged_name'])) for r in meta['references']]
    ref_inputs={canonical(v) for _,d in refs for v in walk(d) if {'request','product','sources','features'}.issubset(v)}
    ref_sources=[v for _,d in refs for v in walk(d) if isinstance(v.get('id'),str) and isinstance(v.get('text'),str)]
    ref_ids={v['id'] for v in ref_sources};ref_text={normalized(v['text']) for v in ref_sources}
    rows=[];all_sources=[]
    for r in meta['inputs']:
        data=load(root/r['staged_name']);raw=(root/r['staged_name']).read_bytes()
        errors=list(Draft202012Validator(schema).iter_errors(data))
        exact=canonical(data) in ref_inputs
        source_ids=[s['id'] for s in data['sources'] if s['id'] in ref_ids]
        source_text=[sha256(s['text'].encode('utf-8')).hexdigest() for s in data['sources'] if normalized(s['text']) in ref_text]
        rows.append({'case_id':r['case_id'],'role':r['role'],'group_id':r['group_id'],
            'input_sha256':sha256(raw).hexdigest(),'canonical_input_sha256':canonical(data),
            'schema_error_paths':['/'.join(str(x) for x in e.absolute_path) for e in errors],
            'exact_public_or_legacy_input_match':exact,'public_or_legacy_source_id_matches':source_ids,
            'public_or_legacy_normalized_text_matches':source_text,
            'source_kind':data['product']['source_kind'],'model_id':data['product']['model_id'],
            'document_version':data['product']['document_version'],'source_count':len(data['sources']),
            'actual_LG_or_customer_data':False})
        for s in data['sources']:
            all_sources.append({'group':r['group_id'],'id':s['id'],'text':normalized(s['text'])})
    assert len(rows)==7 and sum(r['role']=='primary' for r in rows)==6
    assert all(not r['schema_error_paths'] and not r['exact_public_or_legacy_input_match']
               and not r['public_or_legacy_source_id_matches'] and not r['public_or_legacy_normalized_text_matches'] for r in rows)
    assert all(r['source_kind']=='synthetic' for r in rows)
    cross=[]
    for idx,a in enumerate(all_sources):
        for b in all_sources[idx+1:]:
            if a['group']!=b['group'] and (a['id']==b['id'] or a['text']==b['text']):cross.append((a['id'],b['id']))
    assert not cross
    proof={'status':'candidate_format_and_exact_exposure_checks_PASS','primary_candidates':6,'paired_supplement':1,
        'checked_reference_files':len(refs),'rows':rows,'cross_case_source_duplicates':cross,
        'paired_before_after_same_sources_are_one_evaluation_group':True,
        'semantic_independence_approved':False,'independent_reviewer':None,'private_handoff_route_approved':False,
        'old_eight_public_inputs_resolved':False,'candidate_selected_as_replacement':False,
        'answer_contents_or_demo_data_mounted':False,'model_generation_or_scoring':False,
        'scope_limit':'No exact/normalized match in checked sources does not prove unseen tuning history or semantic independence.'}
    (out/'candidate-validation.json').write_bytes((json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({k:proof[k] for k in ('status','primary_candidates','paired_supplement','checked_reference_files','semantic_independence_approved')},ensure_ascii=False))
if __name__=='__main__':main()
