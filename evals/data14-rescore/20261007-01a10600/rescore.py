"""Full eleven-query offline scorer. Actual PM authority is verified externally."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
def load(path):return json.loads(path.read_bytes())
def canonical(value):return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
def score(ids,gold):
    gold=set(gold)
    rank=next((n for n,k in enumerate(ids[:3],1) if k in gold),None)
    return {'hit_at_1':int(bool(ids) and ids[0] in gold),'recall_at_3':len(set(ids[:3])&gold)/len(gold),'mrr_at_3':1/rank if rank else 0.0}
def approval_allows(receipt,gold):
    if receipt is None:return False
    return (receipt.get('owner')=='jeongiryang'
        and receipt.get('status')=='verified_PM_gold_approval'
        and receipt.get('scope')=='FR01-and-fixed-11-query-rescore'
        and receipt.get('approved_gold_canonical_sha256')==canonical(gold)
        and isinstance(receipt.get('source_body_sha256'),str) and len(receipt['source_body_sha256'])==64
        and receipt.get('source_url','').startswith('https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/'))
def rescore(attempts,corpus,queries,gold,receipt):
    if not approval_allows(receipt,gold):
        return {'status':'awaiting_verified_PM_gold_approval','official_11_question_metrics':None,
            'new_search_model_calls':0,'meaning':'A file/boolean alone does not authenticate authority; the dispatcher must verify actual GitHub owner/body/scope.'}
    assert len(attempts)==225 and len({a['attempt_id'] for a in attempts})==225
    cq={r['id']:r for r in queries};ce={r['id']:r for r in corpus}
    assert len(gold['rows'])==11 and len({r['query_id'] for r in gold['rows']})==11
    grouped=defaultdict(list)
    for a in attempts:grouped[(a['method'],a['query_id'])].append(a)
    methods=sorted({a['method'] for a in attempts});assert len(methods)==3
    outputs={};per_query=[]
    for method in methods:
        values=[]
        for row in gold['rows']:
            q=cq[row['query_id']];ids=[]
            assert row['approved_evidence']
            for g in row['approved_evidence']:
                e=ce[g['id']]
                assert e['model_id']==q['model_id']==g['model_id']
                assert e['document_version']==q['document_version']==g['document_version']
                assert sha256(e['text'].encode('utf-8')).hexdigest()==g['text_utf8_sha256']
                ids.append(g['id'])
            records=grouped[(method,q['id'])]
            assert len(records)==5 and sorted(a['repeat'] for a in records)==[1,2,3,4,5]
            rankings=[[v['id'] for v in a['top3']] if a['status']=='success' else [] for a in records]
            assert all(r==rankings[0] for r in rankings),'Unequal rankings need explicit repeat aggregation approval'
            value=score(rankings[0],ids);values.append(value)
            per_query.append({'method':method,'query_id':q['id'],'gold_ids':ids,'metrics':value})
        outputs[method]={k:sum(v[k] for v in values)/11 for k in values[0]}
    return {'status':'approved_existing_rankings_rescored','official_11_question_metrics':outputs,'per_query':per_query,
        'quality_denominator_unique_supported_queries':11,'no_gold_cases_excluded':4,'new_search_model_calls':0,
        'original_failed_attempts_retained':True,'independent_quality_claimed':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();i=args.input
    attempts=[json.loads(s) for s in (i/'attempts.jsonl').read_text('utf-8').splitlines()]
    receipt=load(i/'verified-approval.json') if (i/'verified-approval.json').exists() else None
    result=rescore(attempts,load(i/'model-corpus.json'),load(i/'model-queries.json'),load(i/'proposed-gold.json'),receipt)
    args.output.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'status':result['status'],'official_11_question_metrics':result['official_11_question_metrics'],'new_search_model_calls':0},ensure_ascii=False))
if __name__=='__main__':main()
