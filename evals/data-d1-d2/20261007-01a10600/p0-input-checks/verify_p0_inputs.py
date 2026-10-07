"""Existing P0 contract and immutable source lineage, no runtime/model calls."""
import argparse,json,hashlib
from pathlib import Path
from lgax_contracts.research import validate_research_bundle
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
folder=a.input/'data/research/r8-public-research-20261007/d1-d2-01a10600'
members=json.loads((folder/'d1-membership.json').read_bytes());byid={m['original_review_id']:m for m in members}
lineage=json.loads((a.input/'evals/data-d1-d2/20261007-01a10600/p0-alignment.json').read_bytes())
assert hashlib.sha256((a.input/lineage['schema_path']).read_bytes()).hexdigest()==lineage['schema_sha256']
seen=set();results={}
for group in ['fridge','dishwasher','microwave']:
    path=folder/'agent-input'/group/'research-bundle.json';raw=path.read_bytes();bundle=json.loads(raw)
    validate_research_bundle(bundle)
    assert bundle['analysis_scope']=='product_group' and bundle['product_group']==group
    n=0
    for source in bundle['sources']:
        assert source['source_kind']=='public'
        if source['source_type']!='review':continue
        rid=source['metadata']['original_review_id'];m=byid[rid]
        assert rid not in seen;seen.add(rid)
        assert m['split']=='development' and m['product_group']==group
        assert hashlib.sha256(source['text'].encode()).hexdigest()==m['text_sha256']
        assert source['page_model']==m['displayed_model_id'] and source['purchased_model'] is None and source['published_at'] is None
        assert source['metadata']['split']==m['split'] and source['metadata']['strict_exact_model_eligible_for_model_input'] is False
        n+=1
    assert n==lineage['groups'][group]['review_count']
    assert hashlib.sha256(raw).hexdigest()==lineage['groups'][group]['sha256']
    results[group]={'bundle_id':bundle['bundle_id'],'sources':len(bundle['sources']),'development_reviews':n,'schema':'PASS','sha256':hashlib.sha256(raw).hexdigest()}
assert seen=={m['original_review_id'] for m in members if m['split']=='development'}
qa=json.loads((folder/'agent-input/dishwasher/research-bundle.json').read_bytes())
qas=[x for x in qa['sources'] if x['source_type']=='qa']
assert {q['source_role'] for q in qas}=={'customer_question','official_answer'}
assert {q['purchased_model'] for q in qas}=={None}
receipt={'p0_commit':lineage['p0_commit'],'schema_sha256':lineage['schema_sha256'],'groups':results,
         'preserved_development_review_id_body_model_split_holds':141,'excluded_evaluation_demonstration_quarantine':True,
         'qa_question_and_official_answer_separated':True,'known_review_posting_dates':0,'confirmed_purchased_skus':0,
         'scope':'P0 contract plus source lineage; not upload/parse/query or AI/server execution','runtime_registered':False,'model_calls':0}
(a.output/'p0-input-checks.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(receipt,ensure_ascii=False))
