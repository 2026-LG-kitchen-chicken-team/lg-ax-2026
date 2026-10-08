"""Data-only semantic boundary checks and counterexamples; no model or production imports."""
import argparse,json
from copy import deepcopy
from pathlib import Path

def validate_bundle(manual,qa,reviews):
 assert len(manual['models'])==15 and len({r['model_id'] for r in manual['models']})==15
 assert len(manual['manual_references'])==19
 assert len({r['pdf_sha256'] for r in manual['manual_references']})==15
 assert all(r['document_to_model_status']=='CONFIRMED' for r in manual['models'])
 assert sum(r['manual_scope_status']=='CONFIRMED' for r in manual['models'])==5
 assert sum(r['manual_scope_status']=='CONDITIONAL' for r in manual['models'])==10
 assert all(r['optional_feature_status']=='UNCONFIRMED' and not r['all_optional_features_applicable'] for r in manual['models'])
 assert not manual['all_model_features_or_purchase_time_revision_approved']
 expected={'DUE4BGL1E':'빌트인전용','DUE1BGL1E':'빌트인전용','DUE5BGL1E':'빌트인전용','DUE5BGE':'빌트인전용','DFE5BGE':'프리스탠딩겸용'}
 assert {r['model_id']:r['confirmed_value'] for r in manual['verified_feature_branches']}==expected
 assert all(not r['meaning_or_pm_approval'] and not r['runtime_applied_this_task'] for r in manual['manual_references'])
 assert len(qa['candidates'])==3 and all(r['source_type']=='faq' and r['source_role']=='official_document' for r in qa['candidates'])
 assert all(r['individual_customer_question_id'] is None and r['question_author_role']=='manufacturer_public_usage_question' for r in qa['candidates'])
 assert all(r['customer_review_published_at'] is None and not r['eligible_for_customer_discomfort_or_time_denominator'] for r in qa['candidates'])
 assert qa['individual_customer_question_answer_pairs']==0 and qa['confirmed_customer_discomfort_cases']==0 and qa['customer_review_denominator']==0
 assert len(qa['scope_differences'])==2 and all(not r['arbitrary_winner_selected'] and not r['meaning_or_pm_approved'] for r in qa['scope_differences'])
 assert len(reviews['reviews'])==1 and reviews['preserved_original_review_count']==238 and reviews['preserved_development_review_count']==141
 assert reviews['existing_topic_annotations_status']=='draft_unapproved' and not reviews['automatic_append_or_new_topic_approval']
 assert reviews['time_denominator']==0 and reviews['ratio'] is None and reviews['approved_exact_posting_dates']==0
 row=reviews['reviews'][0]
 assert row['source_review_id']=='1253886798' and row['source_item_id']=='1000647425723'
 assert row['displayed_review_date']=='2025.08.02' and row['published_at'] is None
 assert row['purchased_at'] is None and row['purchased_model'] is None and row['first_posting_vs_last_edit_unconfirmed']
 assert not row['time_denominator_eligible'] and not row['runtime_registered'] and not row['pm_approved']
 assert row['original_238_full_normalized_hash_matches']==[] and row['original_238_selected_excerpt_matches']==[]

parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();base=args.input/'data/reference/data-source-followup/20261008-0915-01a10600'
manual=json.loads((base/'manual-applicability.sidecar.json').read_text('utf-8'))
qa=json.loads((base/'usage-qa.sidecar.json').read_text('utf-8'))
reviews=json.loads((base/'review-dates.sidecar.json').read_text('utf-8'))
validate_bundle(manual,qa,reviews)
checks=[{'case':'approved_source_sidecars','passed':True}]
for name,edit in [
 ('shared_manual_promoted_to_all_features',lambda m,q,r:m['models'][0].update(all_optional_features_applicable=True)),
 ('faq_promoted_to_customer_review',lambda m,q,r:q['candidates'][0].update(source_type='review')),
 ('article_date_promoted_to_customer_posting',lambda m,q,r:q['candidates'][0].update(customer_review_published_at='2026-08-04')),
 ('purchase_or_display_date_promoted_to_posting',lambda m,q,r:r['reviews'][0].update(published_at='2025-08-02')),
 ('unapproved_topic_draft_promoted',lambda m,q,r:r.update(existing_topic_annotations_status='approved')),
 ('no_eligible_dates_ratio_zero',lambda m,q,r:r.update(ratio=0.0)),
 ('DUE_and_DFE_installation_branches_mixed',lambda m,q,r:m['verified_feature_branches'][0].update(confirmed_value='프리스탠딩겸용')),
 ('new_reference_marked_runtime_applied',lambda m,q,r:m['manual_references'][0].update(runtime_applied_this_task=True)),
]:
 m,q,r=deepcopy(manual),deepcopy(qa),deepcopy(reviews);edit(m,q,r)
 rejected=False
 try:validate_bundle(m,q,r)
 except AssertionError:rejected=True
 checks.append({'case':name,'passed':rejected})
 assert rejected,name
result={'result':'PASS','valid_sidecar_checks':1,'counterexamples_rejected':len(checks)-1,'checks':checks,
 'scope':'data boundary assertions; not production model quality/API/runtime integration','new_model_or_ocr_calls':0}
args.output.mkdir(parents=True,exist_ok=True)
(args.output/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'result':'PASS','positive_data_validation':1,'counterexamples_rejected':8,'models':15,'qa':3,'review':1,'denominator':0,'ratio':None},ensure_ascii=False))
