import { RESEARCH_TYPE_LABEL } from './research';
import type { ResearchBundle } from './research';

export function ResearchSourceLinks({ ids, bundle, onInspect }: { ids: string[]; bundle: ResearchBundle; onInspect: (id: string) => void }) {
  return <div className="research-citations">{ids.length ? [...new Set(ids)].map(id => {
    const source = bundle.sources.find(item => item.source_id === id);
    return source ? <span key={id}><button type="button" onClick={() => onInspect(id)}>{RESEARCH_TYPE_LABEL[source.source_type]} {bundle.sources.indexOf(source) + 1}<span className="sr-only"> · {id} 원문</span></button><a href={source.url} target="_blank" rel="noopener noreferrer">출처 ↗<span className="sr-only"> {source.title}</span></a></span> : null;
  }) : <span>확인된 자료 없음</span>}</div>;
}
