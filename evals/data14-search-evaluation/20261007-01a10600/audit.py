"""Offline audit of existing rankings; never imports or executes a search model."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import csv
import json
import math
from pathlib import Path

def load(root, name):
    return json.loads((root/name).read_bytes())
def digest(raw):
    return sha256(raw).hexdigest()
def quality(ids, gold):
    gold=set(gold)
    assert gold
    rank=next((n for n,k in enumerate(ids[:3],1) if k in gold),None)
    return {'hit_at_1':int(bool(ids) and ids[0] in gold),
            'recall_at_3':len(set(ids[:3])&gold)/len(gold),'mrr_at_3':1/rank if rank else 0.0}
def save(root,name,data):
    (root/name).write_bytes((json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--input',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    args=cli.parse_args()
    i,o=args.input,args.output
    pins=load(i,'source-pins.json')
    for item in pins['files']:
        assert digest((i/item['staged_name']).read_bytes())==item['sha256']
    corpus=load(i,'model-corpus.json')
    queries=load(i,'model-queries.json')
    protocol=load(i,'comparison-protocol.json')
    mapping=load(i,'question-evidence-map.json')
    provenance=load(i,'retrieval-provenance.json')
    original=load(i,'retrieval-summary.json')
    execution=load(i,'execution.json')
    environment=load(i,'environment.json')
    registered=load(i,'registered-dataset.json')
    attempts=[json.loads(line) for line in (i/'attempts.jsonl').read_text('utf-8').splitlines()]
    assert len(attempts)==225 and len({a['attempt_id'] for a in attempts})==225
    assert execution['status']=='measurement_completed' and execution['measured_attempts']==225
    assert digest((i/'model-corpus.json').read_bytes())==execution['model_corpus_sha256']
    assert digest((i/'model-queries.json').read_bytes())==execution['model_queries_sha256']
    assert digest((i/'comparison-protocol.json').read_bytes())==execution['original_protocol_sha256']
    assert digest((i/'run_retrieval.py.source').read_bytes())==execution['runner_sha256']
    assert len(corpus)==21 and len(queries)==15
    by_id={e['id']:e for e in corpus}
    by_q={q['id']:q for q in queries}
    by_m={r['query_id']:r for r in mapping['rows']}
    by_p={r['id']:r for r in provenance['evidence']}
    by_registered={r['id']:r for r in registered['evidence']}
    corpus_rows=[]
    for e in corpus:
        p=by_p[e['id']]
        original_e=by_registered[e['id']]
        assert all(e[k]==original_e[k] for k in ('id','model_id','document_version','text'))
        text_hash=digest(e['text'].encode('utf-8'))
        assert p['raw_text_sha256']==text_hash
        corpus_rows.append({'id':e['id'],'model_id':e['model_id'],'document_version':e['document_version'],
            'text_utf8_sha256':text_hash,'source_id':original_e['source_id'],'source_kind':original_e['source_kind'],
            'locator':original_e['locator'],'source_url':p['source_url'],
            'declared_pdf_sha256':p['source_pdf_sha256'],'original_position_pin':p['original'],
            'pdf_binary_rehashed_this_audit':False})
    methods=protocol['retrieval']['methods']
    assert Counter(a['method'] for a in attempts)==Counter({m:75 for m in methods})
    grouped=defaultdict(list)
    returned=0
    for a in attempts:
        q=by_q[a['query_id']]
        assert a['requested_model']==q['model_id'] and a['requested_version']==q['document_version']
        assert a['position']==protocol['query_order'].index(q['id'])+1
        assert a['latency_ms']>=0 and math.isfinite(a['latency_ms'])
        assert a['eligible_count']==sum(e['model_id']==q['model_id'] and e['document_version']==q['document_version'] for e in corpus)
        assert len({r['id'] for r in a['top3']})==len(a['top3'])<=3
        for hit in a['top3']:
            e=by_id[hit['id']]
            assert hit['model_id']==e['model_id']==q['model_id']
            assert hit['document_version']==e['document_version']==q['document_version']
            assert hit['raw_text_sha256']==digest(e['text'].encode('utf-8'))
            returned+=1
        grouped[(a['method'],q['id'])].append(a)
    assert returned==630
    for records in grouped.values():
        assert len(records)==5 and sorted(a['repeat'] for a in records)==list(range(1,6))
        rankings=[[r['id'] for r in a['top3']] for a in records]
        assert all(ids==rankings[0] for ids in rankings)
    supported=[r for r in mapping['rows'] if r['ranking_metric_applicable']]
    clear=[r for r in supported if not r['mapping_review_required']]
    no_gold=[r for r in mapping['rows'] if not r['ranking_metric_applicable']]
    assert len(supported)==11 and len(clear)==10 and len(no_gold)==4
    gold_rows=[]
    for r in supported:
        current=[by_p[k] for k in r['unchanged_old_gold_ids']]
        gold_rows.append({'query_id':r['query_id'],'legacy_gold_ids':r['unchanged_old_gold_ids'],
            'gold_exists_in_same_model_document_scope':all(k in by_id and by_id[k]['model_id']==r['model_id']
                and by_id[k]['document_version']==r['requested_document_version'] for k in r['unchanged_old_gold_ids']),
            'gold_text_hashes':{p['id']:p['raw_text_sha256'] for p in current},
            'source_positions':{p['id']:p['locator'] for p in current},
            'mapping_issue':r['mapping_review_required'],'gold_approval_received_this_audit':False})
    assert all(r['gold_exists_in_same_model_document_scope'] for r in gold_rows)
    metrics={}
    for method in methods:
        items=[quality([r['id'] for r in grouped[(method,q['query_id'])][0]['top3']],q['unchanged_old_gold_ids']) for q in clear]
        actual={key:sum(r[key] for r in items)/10 for key in items[0]}
        expected=original['methods'][method]['development_diagnostic_10_queries']
        assert all(math.isclose(actual[k],expected[k],abs_tol=1e-12) for k in actual)
        assert original['methods'][method]['primary_11_question_Hit_at_1'] is None
        metrics[method]={'recomputed_existing_development_10_query_diagnostics':actual,
            'unique_query_denominator':10,'measured_repeats_per_query':5,
            'official_primary_11_Hit_at_1':None,'official_primary_11_Recall_at_3':None,
            'official_primary_11_MRR_at_3':None,'quality_scope':'public development diagnostics, not independent evaluation'}
    fr=by_m['FR-01']
    alternatives=[]
    for identifier in fr['unchanged_old_gold_ids']+fr['proposed_relevant_id_for_PM_review_only']:
        p=by_p[identifier]
        alternatives.append({'id':identifier,'model_id':p['model_id'],'document_version':p['document_version'],
            'text_utf8_sha256':p['raw_text_sha256'],'locator':p['locator'],'source_url':p['source_url'],
            'original_position_pin':p['original'],'approval_status':'not_received',
            'meaning_in_reference': 'lift/remove shelf procedure' if identifier.endswith('-F10') else 'remove food before removing shelf'})
    fr_methods=[]
    for method in methods:
        a=grouped[(method,'FR-01')][0]
        ids=[r['id'] for r in a['top3']]
        old=next(r for r in original['per_query'] if r['method']==method and r['query_id']=='FR-01')
        legacy=quality(ids,fr['unchanged_old_gold_ids'])
        proposed=quality(ids,fr['proposed_relevant_id_for_PM_review_only'])
        assert legacy==old['FR01_legacy_gold_diagnostic'] and proposed==old['FR01_proposed_gold_diagnostic']
        fr_methods.append({'method':method,'unchanged_top3':ids,
            'existing_legacy_gold_diagnostic':legacy,'existing_unapproved_candidate_diagnostic':proposed,
            'new_primary_score':None})
    save(o,'FR01-gold-connection.json',{'query_id':'FR-01','query':fr['query'],
        'alternatives':alternatives,'methods':fr_methods,'gold_changed':False,
        'primary_blocker':'Legacy ID exists but its registered quote describes shelf removal, not food clearance. New relevant ID approval is missing.',
        'existing_scorer_constraint':'PR200 score_retrieval.py asserts 10 certified queries and writes primary_11 as null; an approved mapping alone does not alter that fixed scorer.',
        'no_future_approval_inferred':True})
    nongold_rows=[]
    for r in no_gold:
        for method in methods:
            records=grouped[(method,r['query_id'])]
            a=records[0]
            if r['query_id']=='FR-04':
                assert all(not t['top3'] and t['retrieval_status']=='request_document_version' for t in records)
            nongold_rows.append({'query_id':r['query_id'],'method':method,'attempts':len(records),
                'query':r['query'],'observed_top3_ids':' ; '.join(hit['id'] for hit in a['top3']),
                'retrieval_status':a['retrieval_status'],'declared_expected_response':r['expected_response'],
                'ranking_gold_available':False,'included_in_ranking_quality_denominator':False,
                'actual_answer_or_refusal_question_hold':'not_executed','semantic_pass':None,
                'why_search_is_not_semantic_proof':'Structural scope/empty result does not verify generated rejection, question or hold.'})
    with (o/'no-gold-semantics.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(nongold_rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(nongold_rows)
    save(o,'gold-audit-11.json',{'supported_questions':11,'unambiguous_legacy_mappings':10,
        'unapproved_changed_mapping':'FR-01','rows':gold_rows})
    save(o,'diagnostic-recalculation.json',{'metrics':metrics,'existing_results_only':True,
        'official_11_question_rescoring_executed':False,'new_search_or_model_forward_calls':0})
    save(o,'rescore-preparation.json',{'status':'ready_for_verified_gold_handoff_not_scored',
        'required_PM_input':['approval source URL/owner/time and exact approved gold-file hash',
            'FR-01 accepted evidence ID(s), model/document version/text hash/position',
            'frozen 11-query gold mapping and handling of multiple relevant IDs',
            'PM acceptance of post-measurement gold correction and metric scope'],
        'accepted_gold_ids':None,'approval_reference':None,
        'reuse_after_approval':{'rankings':'same immutable 225 attempts; no model rerun',
            'unit':'11 unique supported queries, each counted once; five repeats are timing repetitions',
            'failure_rule':'failed retrieval counts zero in quality; no dropped attempts',
            'exclude':'four no-gold response-disposition cases',
            'required_scorer_change':'parameterize certified queries and compute primary_11 in a new offline artifact version; preserve PR200 originals'},
        'output_pending':{'macro_Hit_at_1':None,'macro_Recall_at_3':None,'macro_MRR_at_3':None}})
    save(o,'source-evidence-ledger.json',{'rows':corpus_rows,'same_registered_text_hashes':21,
        'original_pdf_binary_rehashed':False,'new_pdf_or_model_files_copied':False})
    save(o,'source-pins.json',pins)
    save(o,'model-pins-consumed.json',{'models':environment['model_files_current_hash_checked'],
        'selected_model_file_count':environment['selected_model_files'],
        'declaration_source':pins['source_PR200_head'],'binary_weights_rehashed_this_audit':False,
        'no_model_or_tokenizer_load':True})
    save(o,'audit-checks.json',{'status':'PASS','existing_attempts_checked':225,'unique_attempts':225,
        'method_query_groups':len(grouped),'returned_evidence_instances_checked':returned,
        'same_registered_original_quotes':21,'old_10_question_metrics_match':True,
        'FR01_original_diagnostics_match':True,'original_gold_and_rankings_modified':False,
        'new_search_inference_calls':0,'new_product_or_OCR_calls':0,'no_gold_cases':4,
        'no_gold_semantic_evaluation_performed':False,'approved_primary_rescore':False})
    print(json.dumps({'attempts':225,'returned_instances':630,'old_diagnostics_match':True,
        'FR01_approval_received':False,'primary_11':None,'search_model_reruns':0},ensure_ascii=False))
if __name__=='__main__':
    main()
