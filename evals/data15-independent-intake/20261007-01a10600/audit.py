"""Deterministic input/provenance audit only; never scores or chooses reviewers."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from jsonschema import Draft202012Validator

def canonical(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
def load(root,name):
    return json.loads((root/name).read_bytes())
def save(root,name,value):
    (root/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
def nodes(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value,list):
        for child in value:
            yield from nodes(child)
def source_records(value):
    return [r for r in nodes(value) if isinstance(r.get('id'),str) and isinstance(r.get('text'),str)]
def hash_text(value):
    return sha256(value.encode('utf-8')).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();i,o=a.input,a.output
    meta=load(i,'bundle-metadata.json')
    for f in meta['staged_files']:
        assert sha256((i/f['staged_name']).read_bytes()).hexdigest()==f['sha256']
    assert meta['input_archive_matches_published_pin'] and meta['review_archive_matches_published_pin']
    assert all(e['source_bytes_equal_zip_bytes'] for b in meta['archives'] for e in b['entries'])
    assert meta['input_archive_forbidden_reviewer_entries']==[]
    manifest=load(i,'cases.json')
    assert manifest['independent_from_development'] is False
    categories=Counter(c['category'] for c in manifest['cases'])
    required=('normal','duplicate_feature','model_version_confusion','conflicting_reviews','missing_evidence','specification_change')
    assert len(manifest['cases'])==6 and set(categories)==set(required)
    schema=load(i,'current-input.schema.json')
    Draft202012Validator.check_schema(schema)
    references=[]
    for f in meta['comparison_references']:
        value=load(i,f['staged_name'])
        sources=source_records(value)
        inputs=[n for n in nodes(value) if {'request','product','sources','features'}.issubset(n)]
        references.append({**f,'ids':{r['id'] for r in sources},
            'text_hashes':{hash_text(r['text']) for r in sources},'input_hashes':{canonical(v) for v in inputs}})
    input_rows=[];ledger=[];overlap_rows=[]
    for f in meta['eight_inputs']:
        value=load(i,f['staged_name'])
        raw=(i/f['staged_name']).read_bytes()
        errors=list(Draft202012Validator(schema).iter_errors(value))
        sources=value['sources']
        ids={r['id'] for r in sources};texts={hash_text(r['text']) for r in sources}
        matches=[]
        for r in references:
            matching_ids=sorted(ids&r['ids']);matching_hashes=sorted(texts&r['text_hashes'])
            exact=canonical(value) in r['input_hashes']
            if matching_ids or matching_hashes or exact:
                matches.append({'reference_path':r['path'],'reference_kind':r['kind'],
                    'reference_sha256':r['sha256'],'matching_ids':matching_ids,
                    'matching_text_sha256':matching_hashes,'exact_full_input_duplicate':exact})
        input_rows.append({'case_id':f['case_id'],'role':f['role'],'archive_path':f['archive_path'],
            'raw_sha256':sha256(raw).hexdigest(),'canonical_input_sha256':canonical(value),
            'schema_errors':[{'path':'/'.join(str(k) for k in e.absolute_path),'validator':e.validator} for e in errors],
            'source_count':len(sources),'declared_product_model':value['product']['model_id'],
            'product_document_version':value['product']['document_version'],
            'source_kinds':sorted({r['source_kind'] for r in sources}),
            'raw_private_text_in_report':False})
        overlap_rows.append({'case_id':f['case_id'],'matches':matches,
            'development_overlap':any(r['reference_kind']=='development' for r in matches),
            'public_heldout_overlap':any(r['reference_kind']=='public_heldout' for r in matches)})
        for n,r in enumerate(sources):
            ledger.append({'case_id':f['case_id'],'source_json_pointer':'/sources/'+str(n),
                'source_id':r['source_id'],'evidence_id':r['id'],'model_id':r['model_id'],
                'document_version':r['document_version'],'source_kind':r['source_kind'],
                'source_type':r['source_type'],'locator':r['locator'],'text_utf8_sha256':hash_text(r['text']),
                'position_meaning':'synthetic logical fixture position; not original LG PDF/CSV physical location',
                'model_document_scope_mismatch':r['model_id']!=value['product']['model_id'] or r['document_version']!=value['product']['document_version'],
                'mismatch_disposition':'recorded; evaluate case-category intent, do not repair the original fixture',
                'original_text_published':False})
    assert len(input_rows)==8 and len(ledger)==16
    assert not any(r['schema_errors'] for r in input_rows)
    dev=sum(r['development_overlap'] for r in overlap_rows)
    public=sum(r['public_heldout_overlap'] for r in overlap_rows)
    assert public==8, 'Do not hide a discrepancy with the prior exposed eight-input record'
    save(o,'input-and-source-audit.json',{'input_count':8,'primary_cases':6,'supplements':2,
        'supplements_are_independent_samples':False,'current_input_schema_passes':8,
        'inputs':input_rows,'source_occurrences':ledger,'no_scores_or_expected_answers':True})
    save(o,'development-and-public-exposure.json',{'comparison_scope':'same 10 development + 7 public-heldout files at fixed current main',
        'reference_count':len(references),'development_files':sum(r['kind']=='development' for r in references),
        'public_heldout_files':sum(r['kind']=='public_heldout' for r in references),
        'inputs_with_development_overlap':dev,'inputs_with_public_heldout_overlap':public,
        'rows':overlap_rows,'original_eight_input_exposure_resolved':False,
        'independent_materials_approved':False,
        'limitation':'No exact match within checked files does not prove unseen training/tuning history or semantic independence.'})
    pm=load(i,'public-PM-manifest.json')
    pm_rows=[]
    for r in meta['public_PM_materials']:
        value=load(i,r['staged_name'])
        payload=value['input']
        data=value['dataset']
        full_hash=canonical(payload)
        pm_rows.append({'case_id':r['case_id'],'category':r['category'],'material_path':r['path'],
            'material_file_sha256':r['sha256'],'canonical_input_sha256':full_hash,
            'input_vs_manifest_request_equal':canonical(payload['request'])==canonical(r['manifest_request']),
            'source_count':len(payload['sources']),'dataset_file_canonical_sha256':canonical(data),
            'exact_development_input_matches':[f['path'] for f in references if f['kind']=='development' and full_hash in f['input_hashes']],
            'source_kind':data['manifest']['source_kind'],'manifest_declared_independent':pm['independent_from_development'],
            'human_independence_or_replacement_approval_received':False,
            'raw_case_or_answer_content_published':False})
    assert len(pm_rows)==6
    save(o,'public-PM-material-reference-audit.json',{'status':'reference_materials_available_not_replacement_authorization',
        'rows':pm_rows,'public_manifest_flag_is_human_approval':False,
        'does_not_resolve_existing_eight_inputs':True})
    save(o,'archive-role-and-hash-audit.json',{'archives':meta['archives'],
        'input_archive_matches_published_pin':True,'review_archive_matches_published_pin':True,
        'input_archive_forbidden_reviewer_entries':[],
        'reviewer_private_answers_parsed_into_this_auditor':False,
        'review_archive_metadata_only':True,'role_separation_kind':'packaging and fixed metadata; not OS access isolation or encryption',
        'external_transfer_confirmed':False,'new_private_delivery_performed':False})
    save(o,'required-intake.json',{'status':'blocked_pending_PM_intake_not_independent_evaluation_done',
        'required_inputs':[{'item':'PM disposition for exposed eight inputs','received':False,
            'needed':'Exact approval reference and choice of diagnostic reuse or replacement; DATA does not choose.'},
            {'item':'Approved new evaluation input-only bundle','received':False,
             'needed':'Versioned manifest for six types + full data/source/model/document/position hashes, fixed schema and provenance, input-only entry list.'},
            {'item':'Separate reviewer-only materials','received':False,
             'needed':'Approved role/recipient manifest and immutable answer/rubric hashes; never feed answers to development or generation.'},
            {'item':'Independent reviewer and approved private path','received':False,
             'needed':'PM-approved reviewer identity/role and recipient-specific private channel; no token in GitHub.'},
            {'item':'Actual complete Agent and strong-baseline bundles','received':False,
             'needed':'Matching code/model/input/data/schema/settings/budgets and untruncated whole-input delivery, raw failures/calls/tokens included.'}],
        'available_legacy_input_bundle':'Verified eight exposed inputs, pending independence; not newly approved',
        'available_public_PM_reference_bundle':'Six declared categories, not evidence of private replacement/independent approval',
        'evaluator_assigned_here':False,'material_disposition_chosen_here':False,
        'model_execution_or_independent_scoring':False})
    save(o,'source-pins.json',{k:v for k,v in meta.items() if k not in ('archives',)})
    save(o,'audit-checks.json',{'status':'PASS_for_intake_audit_only','input_schema_checks':8,
        'source_occurrences':16,'archive_entries_checked':sum(len(b['entries']) for b in meta['archives']),
        'archive_entry_byte_mismatches':0,'development_overlap_inputs':dev,'public_overlap_inputs':public,
        'reference_files':len(references),'public_PM_reference_cases':6,
        'independence_approved':False,'new_independent_scores':None,
        'new_Agent_baseline_model_OCR_execution':0})
    print(json.dumps({'legacy_inputs':8,'source_occurrences':16,'schema_pass':8,
        'development_overlap_inputs':dev,'public_heldout_overlap_inputs':public,
        'archive_entry_checks':sum(len(b['entries']) for b in meta['archives']),
        'independence_approved':False,'new_model_or_scoring_execution':0},ensure_ascii=False))
if __name__=='__main__':
    main()
