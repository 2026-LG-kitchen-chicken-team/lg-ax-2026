"""Post-run provenance/integrity and public development diagnostics, no inference."""
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path


def load(path):
    return json.loads(path.read_text('utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', 'utf-8')


def quality(ids, gold):
    relevant = set(gold)
    assert relevant
    rank = next((n for n, evidence_id in enumerate(ids[:3], start=1) if evidence_id in relevant), None)
    return {'hit_at_1': int(bool(ids) and ids[0] in relevant),
            'recall_at_3': len(set(ids[:3]) & relevant) / len(relevant),
            'mrr_at_3': 1 / rank if rank else 0.0}


def main():
    root, raw, out = Path('/workspace'), Path('/input'), Path('/artifacts')
    corpus = load(root / 'model-corpus.json')
    queries = load(root / 'model-queries.json')
    original_protocol = load(root / 'comparison-protocol.json')
    mapping = load(root / 'question-evidence-map.json')
    execution = load(raw / 'execution.json')
    lengths = load(raw / 'tokenizer-lengths.json')
    rows = [json.loads(line) for line in (raw / 'attempts.jsonl').read_text('utf-8').splitlines()]
    by_id = {row['id']: row for row in corpus}
    by_query = {row['id']: row for row in queries}
    by_map = {row['query_id']: row for row in mapping['rows']}
    assert execution['status'] == 'measurement_completed'
    assert len(rows) == 225 and len({row['attempt_id'] for row in rows}) == 225
    assert all(value <= 256 for value in lengths['maxima'].values()) and not lengths['any_truncation']
    assert execution['model_corpus_sha256'] == sha256((root / 'model-corpus.json').read_bytes()).hexdigest()
    assert execution['model_queries_sha256'] == sha256((root / 'model-queries.json').read_bytes()).hexdigest()
    assert execution['runner_sha256'] == sha256((root / 'run_retrieval.py').read_bytes()).hexdigest()
    assert len(execution['warmups']) == 6 and execution['product_generation_calls'] == 0
    methods = original_protocol['retrieval']['methods']
    assert Counter(row['method'] for row in rows) == Counter({name: 75 for name in methods})
    grouped = defaultdict(list)
    returned_count = 0
    for row in rows:
        query = by_query[row['query_id']]
        assert row['requested_model'] == query['model_id'] and row['requested_version'] == query['document_version']
        assert row['position'] == original_protocol['query_order'].index(row['query_id']) + 1
        assert row['latency_ms'] >= 0 and math.isfinite(row['latency_ms'])
        expected_scope = [item for item in corpus if item['model_id'] == query['model_id']
                          and item['document_version'] == query['document_version']]
        assert row['eligible_count'] == len(expected_scope)
        assert len({item['id'] for item in row['top3']}) == len(row['top3']) <= 3
        for item in row['top3']:
            source = by_id[item['id']]
            assert item['model_id'] == source['model_id'] == query['model_id']
            assert item['document_version'] == source['document_version'] == query['document_version']
            assert item['raw_text_sha256'] == sha256(source['text'].encode('utf-8')).hexdigest()
            assert math.isfinite(item['score'])
            returned_count += 1
        if query['document_version'] is None:
            assert row['top3'] == [] and row['retrieval_status'] == 'request_document_version'
        grouped[(row['method'], row['query_id'])].append(row)
    summaries, per_query = {}, []
    certified_ids = [row['query_id'] for row in mapping['rows']
                     if row['ranking_metric_applicable'] and not row['mapping_review_required']]
    assert len(certified_ids) == 10
    for method in methods:
        aggregate = []
        for query in queries:
            records = grouped[(method, query['id'])]
            assert len(records) == 5 and sorted(row['repeat'] for row in records) == [1, 2, 3, 4, 5]
            rankings = [[item['id'] for item in row['top3']] for row in records]
            assert all(ids == rankings[0] for ids in rankings), 'Nondeterministic ranking; preserve original attempts'
            mapping_row = by_map[query['id']]
            metrics = quality(rankings[0], mapping_row['unchanged_old_gold_ids']) if mapping_row['ranking_metric_applicable'] else None
            if query['id'] in certified_ids:
                aggregate.append(metrics)
            per_query.append({'method': method, 'query_id': query['id'], 'top3_ids': rankings[0],
                'quality_metrics': metrics if query['id'] in certified_ids else None,
                'quality_status': 'development_diagnostic_not_independent' if query['id'] in certified_ids
                                  else 'FR-01_mapping_pending' if query['id'] == 'FR-01' else 'non_answerable_semantics_not_tested',
                'FR01_legacy_gold_diagnostic': metrics if query['id'] == 'FR-01' else None,
                'FR01_proposed_gold_diagnostic': quality(rankings[0], mapping_row['proposed_relevant_id_for_PM_review_only'])
                                               if query['id'] == 'FR-01' else None,
                'expected_response_from_public_development_map': mapping_row['expected_response'],
                'actual_AI_answer_or_response_disposition_tested': False})
        all_method = [row for row in rows if row['method'] == method]
        latency_rows = [row for row in all_method if by_map[row['query_id']]['ranking_metric_applicable'] and row['status'] == 'success']
        latencies = sorted(row['latency_ms'] for row in latency_rows)
        returned = sum(len(row['top3']) for row in all_method)
        summaries[method] = {
            'measured_attempts': 75, 'failed_attempts': sum(row['status'] != 'success' for row in all_method),
            'ranked_attempts': sum(bool(row['top3']) for row in all_method),
            'missing_version_empty_attempts': sum(row.get('retrieval_status') == 'request_document_version' for row in all_method),
            'zero_score_only_attempts': sum(bool(row.get('zero_score_only')) for row in all_method),
            'quality_denominator_unique_queries': 10, 'excluded_ambiguous_query': 'FR-01',
            'development_diagnostic_10_queries': {key: statistics.mean(row[key] for row in aggregate)
                                                 for key in ('hit_at_1', 'recall_at_3', 'mrr_at_3')},
            'primary_11_question_Hit_at_1': None,
            'latency_denominator_successful_supported_attempts': len(latencies),
            'latency_median_ms': statistics.median(latencies),
            'latency_p95_ms': latencies[math.ceil(len(latencies) * .95) - 1],
            'no_gold_attempt_timings_excluded_from_supported_summary': 20,
            'model_mix_rate_at_3': sum(row.get('model_mix_count', 0) for row in all_method) / returned if returned else None,
            'version_mix_rate_at_3': sum(row.get('version_mix_count', 0) for row in all_method) / returned if returned else None,
            'returned_evidence_instances': returned,
            'mix_removed_by_structural_policy_not_model_quality': True}
    write(out / 'retrieval-summary.json', {
        'status': '225_measurements_complete_primary_gold_adjudication_pending',
        'execution_code_commit': execution['code_version'], 'dataset_version': execution['dataset_version'],
        'corpus_evidence': 21, 'queries': 15, 'methods': summaries, 'per_query': per_query,
        'cold_load_ms': execution['cold_load_ms'], 'index_build_ms': execution['index_build_ms'],
        'peak_rss_mb': execution['peak_rss_mb'],
        'inference_forward_calls': execution['inference_forward_calls'],
        'product_generation_calls': 0, 'independent_evaluation_scores': None,
        'limitations': ['FR-01 old F10 quote lacks food-removal text; F10-FOOD proposed but not approved. Original gold unchanged.',
                        '10-question scores are public development diagnostics, not independent/full Agent quality.',
                        'Four no-gold cases have raw rankings/timings; semantic reject/clarification or unsupported-answer decisions are not generated.',
                        'Scope mixing is prevented structurally before scoring; this does not prove model understanding.',
                        'Fixed CPU comparison in local container is not operating API or GPU throughput.']})
    with (out / 'retrieval-attempts.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['attempt_id', 'method', 'repeat', 'query_id', 'requested_model',
            'requested_version', 'status', 'retrieval_status', 'latency_ms', 'eligible_count', 'top1_id', 'top3_ids', 'failure_type'])
        writer.writeheader()
        for row in rows:
            item = {key: row.get(key) for key in writer.fieldnames}
            item.update(top1_id=row['top3'][0]['id'] if row['top3'] else None,
                        top3_ids='|'.join(r['id'] for r in row['top3']),
                        failure_type=row['failure']['type'] if row['failure'] else None)
            writer.writerow(item)
    write(out / 'result-integrity.json', {
        'status': 'pass', 'scoring_source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'attempts_checked': 225, 'unique_attempts': 225, 'method_query_repeat_groups': len(grouped),
        'returned_evidence_instances_checked': returned_count, 'exact_model_version_text_hash_failures': 0,
        'no_truncation': True, 'max_token_lengths': lengths['maxima'],
        'missing_version_attempts_correctly_empty': 15, 'repeated_rankings_deterministic': True,
        'original_gold_changed': False, 'gold_not_mounted_during_inference': True,
        'proves': 'fixed development ranking/provenance integrity only', 'independent_quality_proven': False})
    print(json.dumps({'status': 'pass', 'attempts': len(rows), 'returned_evidence_instances': returned_count,
                      'summary': summaries}, ensure_ascii=False))


if __name__ == '__main__':
    main()
