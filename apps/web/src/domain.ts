export type ProductGroup = 'fridge' | 'dishwasher' | 'microwave';
export type View = 'request' | 'evidence' | 'concepts' | 'history' | 'trends';

export interface Product {
  id?: string;
  model_id: string;
  product_group: ProductGroup;
  name?: string;
  label?: string;
  document_version?: string;
  [key: string]: unknown;
}

export interface Evidence {
  id: string;
  model_id: string;
  document_version: string;
  source_kind: string;
  source_type: string;
  source_id: string;
  locator: { page?: number; row?: number; section?: string; [key: string]: unknown };
  text: string;
  feature_ids: string[];
  [key: string]: unknown;
}

export interface BootstrapData {
  products: Product[];
  evidence: Evidence[];
  reviews: unknown[];
  features: { id: string; name: string; [key: string]: unknown }[];
  manifest: Record<string, unknown>;
  contract_version: string;
  [key: string]: unknown;
}

export const SCENARIOS = [
  { group: 'fridge', title: '냉장고', subtitle: '청소와 수납', prompt: '냉장고를 청소할 때 느끼는 불편을 줄일 기능을 찾아줘.', situation: '음료를 쏟은 뒤 선반과 식품을 옮겨 청소하는 상황' },
  { group: 'dishwasher', title: '식기세척기', subtitle: '적재와 사용 안내', prompt: '서로 다른 크기의 식기를 넣을 때 남는 불편을 검토해줘.', situation: '여러 종류의 식기를 함께 적재하는 상황' },
  { group: 'microwave', title: '전자레인지', subtitle: '반복 설정과 중복 검토', prompt: '조리 설정을 반복할 때의 불편이 기존 기능으로 해결되는지 검토해줘.', situation: '자주 사용하는 조리 설정을 다시 입력하는 상황' },
] as const;

export function productName(product: Product): string {
  return product.name ?? product.label ?? product.model_id;
}

/** Describes the connected sources, not whether an Agent ran or the dataset represents market demand. */
export function bootstrapSourceSummary(data: BootstrapData): string {
  const labels: Record<string, string> = { synthetic: '합성자료', public: '공개자료', licensed: '이용허락 자료', private: '비공개 자료' };
  const kinds = new Set(data.evidence.map(item => item.source_kind));
  if (typeof data.manifest.source_kind === 'string') kinds.add(data.manifest.source_kind);
  const origins = [...new Set([...kinds].map(kind => Object.hasOwn(labels, kind) ? labels[kind] : '출처 미확인'))].sort();
  const source = origins.length > 1 ? `혼합자료 (${origins.join(' · ')})` : origins[0] ?? '출처 미확인';
  const version = typeof data.manifest.version === 'string' && data.manifest.version ? data.manifest.version : '버전 미확인';
  return `${source} · 자료 ${version}`;
}

export function evidenceLocation(evidence: Evidence): string {
  const parts: string[] = [];
  if (evidence.locator.page !== undefined) parts.push(`${evidence.locator.page}쪽`);
  if (evidence.locator.row !== undefined) parts.push(`${evidence.locator.row}행`);
  if (evidence.locator.section) parts.push(evidence.locator.section);
  return parts.join(' · ') || '위치 정보 없음';
}

export function filterEvidence(evidence: Evidence[], options: { modelId: string; query: string; type: string }): Evidence[] {
  const query = options.query.trim().toLocaleLowerCase('ko');
  return evidence.filter(item => (!options.modelId || item.model_id === options.modelId)
    && (options.type === 'all' || item.source_type === options.type)
    && (!query || `${item.text} ${item.id} ${item.model_id} ${item.locator.section ?? ''}`.toLocaleLowerCase('ko').includes(query)));
}

export function friendlyError(error: unknown): string {
  return error instanceof Error ? error.message : '요청 중 알 수 없는 오류가 발생했습니다.';
}
