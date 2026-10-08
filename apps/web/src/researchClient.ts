import { ApiError } from './api';
import { parseBundleList, parsePlanningBrief, parseResearchBundle } from './research';
import type { PlanningBrief, ResearchBundle, ResearchGuideExport, ResearchGuideInput, ResearchPlanningInput } from './research';
import { normalizeSourceSelection, planningInputScope } from './researchSelection';

const OFFICIAL_GUIDE_DOMAINS = ['lge.com', 'lge.co.kr', 'samsung.com', 'samsungsvc.co.kr'];
function originalSnapshot(value: unknown): string {
  return JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.entries(item).sort(([left], [right]) => left.localeCompare(right))) : item);
}

/** Research requests reuse workspace Bearer authorization; credentials stay in a caller-owned memory closure. */
export class ResearchClient {
  private readonly bundleHashes = new Map<string, string>();
  constructor(private readonly credential: () => string, private readonly transport: typeof fetch = (input, init) => fetch(input, init)) {}
  private async request(path: string, signal?: AbortSignal, input?: ResearchPlanningInput | ResearchGuideInput): Promise<unknown> {
    const token = this.credential();
    if (token.length < 32 || token.length > 256 || /\s/.test(token)) throw new ApiError('UNAUTHORIZED', '작업실 토큰을 확인해 주세요.');
    let response: Response;
    try {
      response = await this.transport(`/api/research/${path}`, {
        signal, method: input ? 'POST' : 'GET', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', 'X-LGAX-Client': 'web' },
        ...(input ? { body: JSON.stringify(input) } : {}),
      });
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') throw error;
      throw new ApiError('RESEARCH_UNAVAILABLE', '실제 자료 기획 서버에 연결할 수 없습니다. 연결을 확인한 뒤 다시 시도해 주세요.');
    }
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const modelRequest = Boolean(input && path === 'planning-runs');
      const pendingMessage = modelRequest
        ? '실제 자료 조회는 연결됐습니다. 모델 실행 활성화를 기다리고 있습니다.'
        : path === 'guides' ? '공식 자료 안내서 API 연결 대기 중입니다. 원문 조회와 선택은 계속 사용할 수 있습니다.'
          : '실제 자료 기획 API 연결 대기 중입니다. 연결이 준비되면 자료 조회와 기획 실행을 사용할 수 있습니다.';
      if (body && typeof body === 'object' && 'error' in body && body.error && typeof body.error === 'object') {
        const error = body.error as Record<string, unknown>;
        if (error.code === 'NOT_IMPLEMENTED' || error.code === 'RESEARCH_NOT_READY') {
          throw new ApiError(modelRequest ? 'MODEL_PENDING' : 'RESEARCH_PENDING', pendingMessage);
        }
        throw new ApiError(typeof error.code === 'string' ? error.code : 'RESEARCH_FAILED', typeof error.message === 'string' ? error.message : '기획 요청을 처리하지 못했습니다.');
      }
      if ([404, 501, 503].includes(response.status)) throw new ApiError(modelRequest ? 'MODEL_PENDING' : 'RESEARCH_PENDING', pendingMessage);
      throw new ApiError('RESEARCH_FAILED', `기획 요청이 HTTP ${response.status} 오류로 종료됐습니다.`);
    }
    if (body === null) throw new ApiError('CONTRACT_MISMATCH', '실제 자료 기획 응답을 JSON으로 읽을 수 없습니다.');
    return body;
  }
  async listBundles(signal?: AbortSignal) {
    const bundles = parseBundleList(await this.request('bundles', signal));
    this.bundleHashes.clear();
    for (const bundle of bundles) if (bundle.bundle_sha256) this.bundleHashes.set(bundle.bundle_id, bundle.bundle_sha256);
    return bundles;
  }
  private checkHash(brief: PlanningBrief): void {
    const expected = this.bundleHashes.get(brief.bundle_id);
    if (expected && brief.runtime.bundle_sha256 !== expected) throw new ApiError('DATASET_MISMATCH', '기획 결과의 자료 버전이 선택한 원문과 다릅니다. 다시 연결해 자료를 확인해 주세요.');
  }
  async getBundle(id: string, signal?: AbortSignal): Promise<ResearchBundle> {
    const bundle = parseResearchBundle(await this.request(`bundles/${encodeURIComponent(id)}`, signal));
    if (bundle.bundle_id !== id) throw new ApiError('CONTRACT_MISMATCH', '요청한 실제 자료와 응답 ID가 다릅니다.');
    return bundle;
  }
  async createPlan(bundle: ResearchBundle, input: ResearchPlanningInput, previous: PlanningBrief | null, signal?: AbortSignal): Promise<PlanningBrief> {
    if (input.bundle_id !== bundle.bundle_id || !input.goal.trim() || previous && previous.bundle_id !== bundle.bundle_id
        || (input.previous_run_id ?? null) !== (previous?.run_id ?? null)) throw new ApiError('INVALID_ARGUMENT', '자료·목적·기준 실행을 확인해 주세요.');
    const inherited = previous ? planningInputScope(previous, bundle) : null;
    const selectedIds = input.selected_source_ids === undefined ? undefined : normalizeSourceSelection(bundle, input.selected_source_ids);
    if (previous && selectedIds && JSON.stringify(selectedIds) !== JSON.stringify(inherited?.ids ?? previous.source_facts.map(item => item.source_id))) {
      throw new ApiError('DATASET_MISMATCH', '조건 변경은 이전 입력 범위를 유지합니다. 다른 근거는 새 기획으로 시작해 주세요.');
    }
    const hash = this.bundleHashes.get(bundle.bundle_id);
    if (input.bundle_sha256 !== undefined && hash && input.bundle_sha256 !== hash) throw new ApiError('DATASET_MISMATCH', '선택한 자료 버전이 달라졌습니다. 다시 연결해 주세요.');
    const request = { ...input, ...(selectedIds ? { selected_source_ids: selectedIds } : {}), ...(hash ? { bundle_sha256: hash } : {}) };
    const brief = parsePlanningBrief(await this.request('planning-runs', signal, request), bundle);
    this.checkHash(brief);
    const scope = planningInputScope(brief, bundle);
    const expected = previous ? inherited : { kind: selectedIds ? 'user_selected_sources' : 'full_bundle', ids: selectedIds ?? bundle.sources.map(source => source.source_id) };
    if (((selectedIds || inherited) && !scope) || (scope && expected && (scope.kind !== expected.kind || JSON.stringify(scope.ids) !== JSON.stringify(expected.ids)))) {
      throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 입력 근거 범위가 요청과 다릅니다.');
    }
    if (brief.goal !== input.goal || JSON.stringify(brief.constraints) !== JSON.stringify(input.constraints)
        || brief.previous_brief_id !== (previous?.brief_id ?? null) || previous && brief.revision !== previous.revision + 1) {
      throw new ApiError('CONTRACT_MISMATCH', '기획 결과의 목적·조건·수정 연결이 요청과 다릅니다.');
    }
    return brief;
  }
  async getPlan(bundle: ResearchBundle, id: string, signal?: AbortSignal): Promise<PlanningBrief> {
    const brief = parsePlanningBrief(await this.request(`planning-runs/${encodeURIComponent(id)}`, signal), bundle);
    this.checkHash(brief);
    planningInputScope(brief, bundle);
    if (brief.run_id !== id) throw new ApiError('CONTRACT_MISMATCH', '요청한 실행과 결과 ID가 다릅니다.');
    return brief;
  }
  async createGuide(bundle: ResearchBundle, sourceIds: string[], signal?: AbortSignal): Promise<ResearchGuideExport> {
    const ids = normalizeSourceSelection(bundle, sourceIds);
    const wanted = new Set(ids); const sources = bundle.sources.filter(source => wanted.has(source.source_id));
    const unsupported = sources.filter(source => {
      let host = ''; try { host = new URL(source.url).hostname.toLowerCase(); } catch { return true; }
      return source.source_kind !== 'public' || !['manual', 'faq', 'installation', 'qa'].includes(source.source_type)
        || !['official_document', 'official_answer'].includes(source.source_role)
        || !OFFICIAL_GUIDE_DOMAINS.some(domain => host === domain || host.endsWith(`.${domain}`));
    });
    if (unsupported.length) throw new ApiError('INVALID_ARGUMENT', `공식 설명서·FAQ·설치 안내·공식 답변만 선택해 주세요. 제외할 자료: ${unsupported.map(source => source.source_id).join(', ')}. 선택을 자동으로 누락하지 않습니다.`);
    const hash = this.bundleHashes.get(bundle.bundle_id);
    const raw = await this.request('guides', signal, { bundle_id: bundle.bundle_id, source_ids: ids, ...(hash ? { bundle_sha256: hash } : {}) });
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new ApiError('CONTRACT_MISMATCH', '공식 자료 안내서 응답을 확인할 수 없습니다.');
    const result = raw as ResearchGuideExport; const guide = result.guide;
    if (result.bundle_id !== bundle.bundle_id || typeof result.bundle_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(result.bundle_sha256)
        || hash && result.bundle_sha256 !== hash) throw new ApiError('DATASET_MISMATCH', '공식 자료 안내서의 자료 ID·버전이 선택한 원문과 다릅니다.');
    if (!guide || guide.guide_version !== '1.0' || guide.guide_kind !== 'official_reference' || guide.bundle_id !== bundle.bundle_id
        || guide.proposal !== null || guide.exact_sku_applicability_confirmed !== false
        || typeof guide.title !== 'string' || !guide.title.trim() || typeof guide.notice !== 'string' || !guide.notice.trim()
        || originalSnapshot(result.source_ids) !== originalSnapshot(ids) || originalSnapshot(guide.sources) !== originalSnapshot(sources)
        || typeof result.markdown !== 'string' || !result.markdown.trim() || typeof result.html !== 'string' || !result.html.trim()) {
      throw new ApiError('CONTRACT_MISMATCH', '공식 자료 안내서의 선택 근거·원문·사실·적용 범위가 원자료와 다릅니다.');
    }
    return result;
  }
}
