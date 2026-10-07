/** Shared authenticated API adapter for the planner UI; credential stays in caller memory. */
import Ajv2020 from 'ajv/dist/2020';
import schema from '../../../packages/contracts/schemas/lgax.schema.json';
import { ApiError } from './api';
import type { BootstrapData } from './domain';

const ajv = new Ajv2020({ allErrors: true, strict: false });
ajv.addFormat('date', { type: 'string', validate: value => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) && new Date(timestamp).toISOString().slice(0, 10) === value;
} });
ajv.addFormat('date-time', { type: 'string', validate: value => /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value)) });
ajv.addSchema(schema, 'workspace');
const contracts = new Map<string, ReturnType<typeof ajv.compile>>();
// Call the browser API as a global function, never as a WorkspaceClient method.
const defaultTransport: typeof fetch = (input, init) => fetch(input, init);
function check(name: string, value: unknown): void {
  let validator = contracts.get(name);
  if (!validator) {
    validator = ajv.compile({ $ref: `workspace#/$defs/${name}` });
    contracts.set(name, validator);
  }
  if (!validator(value)) throw new ApiError('CONTRACT_MISMATCH', '작업실 데이터가 공통 규격과 다릅니다.');
}

// The envelope allows a generic object, but these views require canonical Need/Gap arrays.
// Reject malformed partial output before a rendering component can treat it as analysis.
function checkPlanningOutput(snapshot: WorkspaceRun): void {
  if (snapshot.output === null) return;
  const { needs, gaps } = snapshot.output;
  if (!Array.isArray(needs) || !Array.isArray(gaps)) {
    throw new ApiError('CONTRACT_MISMATCH', '판단 결과에 불편·대조 목록이 필요합니다.');
  }
  for (const need of needs) check('Need', need);
  for (const gap of gaps) check('Gap', gap);
}

export interface WorkspaceProject {
  project: { id: string; name: string; request: Record<string, unknown>; status: string; dataset_version: string };
  owner_id: string;
  document_versions: Record<string, string>;
  dataset_sha256: string;
  created_at: string;
}

export interface WorkspaceRun {
  run: { id: string; project_id: string; status: string; concepts: unknown[]; unresolved: string[]; revision_count: number; [key: string]: unknown };
  request: Record<string, unknown>;
  previous_run_id: string | null;
  request_revision: number;
  actor_id: string;
  client: string;
  document_versions: Record<string, string>;
  dataset_sha256: string;
  created_at: string;
  unconfirmed: string[];
  output: Record<string, unknown> | null;
}

/** PM-owned API contracts; dates/annotations are approved on the server, never submitted here. */
export interface ReviewTrendFilters {
  project_id: string; model_id: string; source_ids: string[]; dataset_version: string;
  start_date: string; end_date_exclusive: string; granularity: 'month' | 'season' | 'year';
  topic_ids: string[]; source_kind: 'synthetic' | 'public' | 'licensed' | 'private';
  timezone: 'Asia/Seoul';
}
export interface ReviewTrendData {
  aggregate: {
    aggregate_id: string; project_id: string; filters: ReviewTrendFilters;
    counts: Record<string, number>; buckets: Array<Record<string, unknown>>;
    warnings: string[]; [key: string]: unknown;
  };
  contract_version: string;
}
export interface TrendEvidenceData {
  project_id: string; aggregate_id: string; bucket_id: string; topic_id: string;
  offset: number; limit: number; total: number; next_offset: number | null;
  evidence: Array<Record<string, unknown>>; contract_version: string;
}

function identifier(id: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$/.test(id)) throw new ApiError('INVALID_ARGUMENT', '프로젝트/실행 ID 형식을 확인해 주세요.');
  return id;
}

export class WorkspaceClient {
  private readonly base: string;
  constructor(base: string, private readonly credential: () => string, private readonly transport: typeof fetch = defaultTransport) {
    if (base) {
      const parsed = new URL(base);
      if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname)
          || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) {
        throw new ApiError('INVALID_ARGUMENT', '로컬 작업실 서버 주소를 확인해 주세요.');
      }
    }
    this.base = base.replace(/\/$/, '');
  }

  private async request<T>(method: string, path: string, contract: string, input?: unknown): Promise<T> {
    const token = this.credential();
    if (!token || token.length < 32 || token.length > 256 || /\s/.test(token)) throw new ApiError('UNAUTHORIZED', '작업실 인증이 필요합니다.');
    let response: Response;
    try {
      response = await this.transport(`${this.base}/api/workspace${path}`, {
        method, credentials: 'omit', redirect: 'error', cache: 'no-store',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', 'X-LGAX-Client': 'web' },
        body: input === undefined ? undefined : JSON.stringify(input),
      });
    } catch {
      throw new ApiError('CONNECTION_FAILED', '공통 작업실 서버에 연결할 수 없습니다.');
    }
    const payload: unknown = await response.json().catch(() => null);
    if (path === '/bootstrap' && response.status === 404) {
      throw new ApiError('WORKSPACE_BOOTSTRAP_UNAVAILABLE', '이 작업실 서버는 인증된 자료 조회를 지원하지 않습니다. 서버와 웹의 버전을 확인해 주세요.');
    }
    if (!response.ok) {
      if (payload && typeof payload === 'object' && 'error' in payload) {
        const error = payload.error;
        if (error && typeof error === 'object' && 'code' in error && 'message' in error) {
          throw new ApiError(String(error.code), String(error.message));
        }
      }
      throw new ApiError('CONNECTION_FAILED', '작업실 서버 요청에 실패했습니다.');
    }
    check(contract, payload);
    const data = (payload as { ok: true; data: T }).data;
    if (contract === 'WorkspaceRunResponse') checkPlanningOutput(data as WorkspaceRun);
    if (contract === 'WorkspaceRunsResponse') {
      for (const snapshot of (data as { runs: WorkspaceRun[] }).runs) checkPlanningOutput(snapshot);
    }
    return data;
  }

  listProjects(): Promise<{ projects: WorkspaceProject[]; contract_version: string }> {
    return this.request('GET', '/projects', 'WorkspaceProjectsResponse');
  }
  bootstrap(): Promise<BootstrapData> {
    return this.request('GET', '/bootstrap', 'WorkspaceBootstrapResponse');
  }
  createProject(name: string, request: Record<string, unknown>, documentVersions: Record<string, string>): Promise<WorkspaceProject> {
    const input = { name, request, document_versions: documentVersions };
    check('WorkspaceProjectCreateRequest', input);
    return this.request('POST', '/projects', 'WorkspaceProjectResponse', input);
  }
  getProject(id: string): Promise<WorkspaceProject> {
    return this.request('GET', `/projects/${identifier(id)}`, 'WorkspaceProjectResponse');
  }
  createRun(projectId: string, request: Record<string, unknown>, previousRunId: string | null = null, unconfirmed: string[] = []): Promise<WorkspaceRun> {
    const input = { request, previous_run_id: previousRunId, unconfirmed };
    check('WorkspaceRunCreateRequest', input);
    return this.request('POST', `/projects/${identifier(projectId)}/runs`, 'WorkspaceRunResponse', input);
  }
  getRun(id: string): Promise<WorkspaceRun> {
    return this.request('GET', `/runs/${identifier(id)}`, 'WorkspaceRunResponse');
  }
  listRuns(projectId: string): Promise<{ runs: WorkspaceRun[]; contract_version: string }> {
    return this.request('GET', `/projects/${identifier(projectId)}/runs`, 'WorkspaceRunsResponse');
  }
  search(projectId: string, q: string, modelId: string): Promise<Record<string, unknown>> {
    const params = new URLSearchParams({ q, model_id: modelId });
    return this.request('GET', `/projects/${identifier(projectId)}/evidence?${params}`, 'WorkspaceEvidenceResponse');
  }

  reviewTrends(filters: ReviewTrendFilters): Promise<ReviewTrendData> {
    check('ReviewTrendRequest', filters);
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (key === 'project_id') continue;
      for (const item of Array.isArray(value) ? value : [value]) params.append(key, String(item));
    }
    return this.request('GET', `/projects/${identifier(filters.project_id)}/review-trends?${params}`,
      'WorkspaceReviewTrendResponse');
  }
  getReviewTrends(projectId: string, aggregateId: string): Promise<ReviewTrendData> {
    return this.request('GET', `/projects/${identifier(projectId)}/review-trends/${identifier(aggregateId)}`,
      'WorkspaceReviewTrendResponse');
  }
  trendEvidence(projectId: string, aggregateId: string, bucketId: string, topicId: string,
    offset = 0, limit = 50): Promise<TrendEvidenceData> {
    const input = { project_id: projectId, aggregate_id: aggregateId, bucket_id: bucketId,
      topic_id: topicId, offset, limit };
    check('ReviewTrendEvidenceRequest', input);
    const params = new URLSearchParams({ bucket_id: bucketId, topic_id: topicId,
      offset: String(offset), limit: String(limit) });
    return this.request('GET', `/projects/${identifier(projectId)}/review-trends/${identifier(aggregateId)}/evidence?${params}`,
      'WorkspaceTrendEvidenceResponse');
  }
}
