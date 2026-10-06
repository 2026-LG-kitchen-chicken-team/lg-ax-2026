"""Offline development ranking measurement; no product generation or gold input."""
import argparse
import importlib.util
import json
import platform
import resource
import socket
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


def load(path):
    return json.loads(path.read_text('utf-8-sig'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', 'utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--code-version', required=True)
    args = parser.parse_args()
    root = Path('/workspace')
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'attempts.jsonl').exists(), 'Preserve previous attempts; use a fresh run directory'
    corpus = load(root / 'model-corpus.json')
    queries = load(root / 'model-queries.json')
    protocol = load(root / 'comparison-protocol.json')
    assert len(corpus) == 21 and len(queries) == 15
    assert all(set(q) == {'id', 'model_id', 'document_version', 'query'} for q in queries)
    assert all(set(row) == {'id', 'model_id', 'document_version', 'text'} for row in corpus)
    assert digest(root / 'model-corpus.json') == protocol['model_corpus_sha256']
    assert digest(root / 'model-queries.json') == protocol['model_queries_sha256']
    query_by_id = {q['id']: q for q in queries}
    order = [query_by_id[qid] for qid in protocol['query_order']]
    assert len(set(protocol['query_order'])) == 15
    source = root / 'model_benchmark.py'
    spec = importlib.util.spec_from_file_location('historical_bm25', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with socket.create_connection(('1.1.1.1', 53), timeout=0.2):
            network_reachable = True
    except OSError:
        network_reachable = False
    assert not network_reachable
    assert not any(Path(p).exists() for p in ('/agent-auth', '/var/run/docker.sock', '/workspace/.git'))
    report = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
              'code_version': args.code_version, 'runner_sha256': digest(Path(__file__)),
              'historical_bm25_source_sha256': digest(source),
              'model_corpus_sha256': digest(root / 'model-corpus.json'),
              'model_queries_sha256': digest(root / 'model-queries.json'),
              'original_protocol_sha256': digest(root / 'comparison-protocol.json'),
              'dataset_version': protocol['dataset_version'], 'split': 'development',
              'measurement_mode': 'raw rankings and provisional metrics; FR-01 gold decision pending',
              'original_protocol_full_acceptance': False,
              'methods': protocol['retrieval']['methods'], 'query_count': 15, 'corpus_count': 21,
              'repeats': 5, 'warmups_per_method': 2, 'query_order': protocol['query_order'],
              'hardware': {'cpu': next((line.split(':', 1)[1].strip() for line in
                  Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown'),
                  'os': platform.platform(), 'python': platform.python_version(),
                  'device': 'cpu', 'cpu_threads': 4, 'container_cpus_limit': 4,
                  'container_memory_limit_bytes': int(Path('/sys/fs/cgroup/memory.max').read_text()),
                  'system_memory_kib': int(next(line.split()[1] for line in
                      Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))},
              'boundary': {'external_network_reachable': network_reachable,
                  'publisher_credentials_mounted': False, 'ai_profile_mounted': False,
                  'host_git_mounted': False, 'docker_socket_mounted': False},
              'cold_load_ms': {}, 'index_build_ms': None, 'warmups': [],
              'inference_forward_calls': {'encoder': 0, 'reranker': 0},
              'product_generation_calls': 0, 'paid_api_calls': 0, 'new_OCR_calls': 0,
              'notes': ['Structural model/version filters do not establish semantic rejection or AI answer correctness.',
                        'No reviewer answers or expected responses were mounted.',
                        'Current API literal_token_count is a separate baseline and was not measured.']}
    write(out / 'execution.json', report)

    def scoped(query):
        if not query['document_version']:
            return []
        return [i for i, item in enumerate(corpus)
                if item['model_id'] == query['model_id']
                and item['document_version'] == query['document_version']]

    def sparse(query):
        indices = scoped(query)
        if not indices:
            return []
        scores = module.bm25(query['query'], [corpus[i]['text'] for i in indices])
        return sorted(zip(indices, scores), key=lambda pair: (-pair[1], corpus[pair[0]]['id']))

    def record_ranking(query, ranking):
        selected = [{'id': corpus[i]['id'], 'model_id': corpus[i]['model_id'],
                     'document_version': corpus[i]['document_version'], 'score': float(score),
                     'raw_text_sha256': sha256(corpus[i]['text'].encode('utf-8')).hexdigest()}
                    for i, score in ranking[:3]]
        return {'retrieval_status': 'request_document_version' if not query['document_version']
                else 'ranked' if selected else 'no_matching_scope',
                'top3': selected, 'zero_score_only': bool(ranking) and all(score == 0 for _, score in ranking),
                'returned_count': len(selected), 'eligible_count': len(scoped(query)),
                'model_mix_count': sum(row['model_id'] != query['model_id'] for row in selected),
                'version_mix_count': sum(row['document_version'] != query['document_version'] for row in selected)}

    def measure(name, function):
        for number, query in enumerate(order[:2], start=1):
            started = time.perf_counter()
            function(query)
            report['warmups'].append({'method': name, 'number': number, 'query_id': query['id'],
                                      'latency_ms': (time.perf_counter() - started) * 1000})
        with (out / 'attempts.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            for repeat in range(1, 6):
                for position, query in enumerate(order, start=1):
                    started = time.perf_counter()
                    try:
                        ranking = function(query)
                        latency = (time.perf_counter() - started) * 1000
                        row = record_ranking(query, ranking) | {'status': 'success', 'failure': None}
                    except Exception as exc:
                        latency = (time.perf_counter() - started) * 1000
                        row = {'status': 'failure', 'failure': {'type': type(exc).__name__, 'message': str(exc)},
                               'top3': [], 'returned_count': 0, 'eligible_count': len(scoped(query))}
                    row.update(attempt_id=f'{name}:R{repeat}:{query["id"]}', method=name,
                               repeat=repeat, position=position, query_id=query['id'],
                               requested_model=query['model_id'], requested_version=query['document_version'],
                               latency_ms=latency)
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                    stream.flush()
                print(json.dumps({'method': name, 'repeat': repeat, 'attempts_so_far_this_method': repeat * 15}), flush=True)
        write(out / 'execution.json', report)

    measure('bm25_filtered', sparse)
    import torch
    import transformers
    from torch.nn import functional
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.manual_seed(20261005)
    report['hardware'].update(torch=torch.__version__, transformers=transformers.__version__,
                              torch_interop_threads=torch.get_num_interop_threads())
    embedding_dir = Path('/embedding')
    reranker_dir = Path('/reranker')
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(embedding_dir, local_files_only=True, trust_remote_code=False)
    embedding_tokenizer_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    rerank_tokenizer = AutoTokenizer.from_pretrained(reranker_dir, local_files_only=True, trust_remote_code=False)
    reranker_tokenizer_ms = (time.perf_counter() - started) * 1000
    report['tokenizer_load_ms'] = {'embedding': embedding_tokenizer_ms, 'reranker': reranker_tokenizer_ms}
    lengths = {'embedding_corpus': [], 'embedding_queries': [], 'reranker_pairs': []}
    for item in corpus:
        lengths['embedding_corpus'].append({'id': item['id'], 'tokens': len(tokenizer(item['text'], truncation=False)['input_ids'])})
    for query in queries:
        lengths['embedding_queries'].append({'id': query['id'], 'tokens': len(tokenizer(query['query'], truncation=False)['input_ids'])})
        for i in scoped(query):
            lengths['reranker_pairs'].append({'query_id': query['id'], 'evidence_id': corpus[i]['id'],
                'tokens': len(rerank_tokenizer(query['query'], corpus[i]['text'], truncation=False)['input_ids'])})
    maxima = {name: max((row['tokens'] for row in rows), default=0) for name, rows in lengths.items()}
    write(out / 'tokenizer-lengths.json', {'max_length': 256, 'maxima': maxima,
                                         'any_truncation': any(n > 256 for n in maxima.values()), 'rows': lengths})
    assert all(n <= 256 for n in maxima.values()), 'Truncation requires a new approved protocol; original attempt preserved'
    started = time.perf_counter()
    encoder = AutoModel.from_pretrained(embedding_dir, local_files_only=True, trust_remote_code=False,
                                       use_safetensors=False, torch_dtype=torch.float32, weights_only=True).eval()
    report['cold_load_ms']['embedding'] = (time.perf_counter() - started) * 1000 + embedding_tokenizer_ms

    def encode(texts):
        batches = []
        with torch.inference_mode():
            for offset in range(0, len(texts), 8):
                inputs = tokenizer(texts[offset:offset + 8], padding=True, truncation=False, return_tensors='pt')
                hidden = encoder(**inputs).last_hidden_state[:, 0]
                report['inference_forward_calls']['encoder'] += 1
                batches.append(functional.normalize(hidden, p=2, dim=1))
        return torch.cat(batches)

    started = time.perf_counter()
    corpus_embeddings = encode([item['text'] for item in corpus])
    report['index_build_ms'] = (time.perf_counter() - started) * 1000

    def dense(query):
        indices = scoped(query)
        if not indices:
            return []
        vector = encode([query['query']])
        scores = (vector @ corpus_embeddings[indices].T)[0].tolist()
        return sorted(zip(indices, scores), key=lambda pair: (-pair[1], corpus[pair[0]]['id']))

    measure('bge_m3_filtered', dense)
    started = time.perf_counter()
    reranker = AutoModelForSequenceClassification.from_pretrained(
        reranker_dir, local_files_only=True, trust_remote_code=False,
        use_safetensors=True, torch_dtype=torch.float32, weights_only=True).eval()
    report['cold_load_ms']['reranker'] = (time.perf_counter() - started) * 1000 + reranker_tokenizer_ms

    def reranked(query):
        candidates = dense(query)[:10]
        if not candidates:
            return []
        indices = [i for i, _ in candidates]
        pairs = [[query['query'], corpus[i]['text']] for i in indices]
        inputs = rerank_tokenizer(pairs, padding=True, truncation=False, return_tensors='pt')
        with torch.inference_mode():
            scores = reranker(**inputs).logits.view(-1).tolist()
            report['inference_forward_calls']['reranker'] += 1
        return sorted(zip(indices, scores), key=lambda pair: (-pair[1], corpus[pair[0]]['id']))

    measure('bge_m3_filtered_reranker', reranked)
    rows = [json.loads(line) for line in (out / 'attempts.jsonl').read_text('utf-8').splitlines()]
    assert len(rows) == 225 and len({row['attempt_id'] for row in rows}) == 225
    report.update(status='measurement_completed', finished_at=datetime.now(timezone.utc).isoformat(),
                  measured_attempts=len(rows), failure_count=sum(row['status'] != 'success' for row in rows),
                  peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    write(out / 'execution.json', report)
    print(json.dumps({'stage': 'completed', 'attempts': len(rows), 'failures': report['failure_count'],
                      'inference_forward_calls': report['inference_forward_calls']}), flush=True)


if __name__ == '__main__':
    main()
