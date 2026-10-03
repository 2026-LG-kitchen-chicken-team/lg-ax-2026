/** Shared authenticated API adapter for the planner UI; credential stays in caller memory. */
import Ajv2020 from 'ajv/dist/2020';
import schema from '../../../packages/contracts/schemas/lgax.schema.json';
import { ApiError } from './api';

const ajv = new Ajv2020({ allErrors: true, strict: false });
ajv.addFormat('date-time', { type: 'string', validate: value => /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value)) });
ajv.addSchema(schema, 'workspace');
const contracts = new Map<string, ReturnType<typeof ajv.compile>>();
function check(name: string, value: unknown): void {
  let validator = contracts.get(name);
  if (!validator) {
    validator = ajv.compile({ $ref: `workspace#/$defs/${name}` });
    contracts.set(name, validator);
  }
  if (!validator(value)) throw new ApiError('CONTRACT_MISMATCH', '작업실 데이터가 공통 규격과 다릅니다.');
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

function identifier(id: string): string {
  if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$/.test(id)) throw new ApiError('INVALID_ARGUMENT', '프로젝트/실행 ID 형식을 확인해 주세요.');
  return id;
}

export class WorkspaceClient {
  private readonly base: string;
  constructor(base: string, private readonly credential: () => string, private readonly transport: typeof fetch = fetch) {
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
    return (payload as { ok: true; data: T }).data;
  }

  listProjects(): Promise<{ projects: WorkspaceProject[]; contract_version: string }> {
    return this.request('GET', '/projects', 'WorkspaceProjectsResponse');
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
}
