import type { ResearchBundle } from './research';

export function ResearchSourceLinks({ ids, bundle, onInspect }: { ids: string[]; bundle: ResearchBundle; onInspect: (id: string) => void }) {
  return <div className="research-citations">{ids.length ? [...new Set(ids)].map(id => {
    const source = bundle.sources.find(item => item.source_id === id);
    return source ? <span key={id}><button type="button" onClick={() => onInspect(id)}>{id} 원문</button><a href={source.url} target="_blank" rel="noopener noreferrer">출처 ↗<span className="sr-only"> {source.title}</span></a></span> : null;
  }) : <span>확인된 자료 없음</span>}</div>;
}
