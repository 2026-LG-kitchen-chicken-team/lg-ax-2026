/** Live-mode connection to the authenticated workspace API (P2-WEB-002); credential stays in React memory only. */
import { useRef, useState } from 'react';
import { ApiError } from './api';
import type { Evidence, Product } from './domain';
import type { PlanningRequest, RunSnapshot } from './planning';
import { WorkspaceClient } from './workspace';
import type { WorkspaceProject } from './workspace';

export interface ErrorView { code: string; title: string; action: string; tone: 'error' | 'notice' }

// Each server failure tells the planner what happened and what to do next; codes are never merged into one message.
const ERROR_VIEWS: Record<string, Omit<ErrorView, 'code'>> = {
  UNAUTHORIZED: { title: '작업실 인증이 필요합니다', action: '작업실 토큰을 다시 입력해 주세요. 토큰은 이 화면의 메모리에만 보관됩니다.', tone: 'error' },
  FORBIDDEN: { title: '이 작업을 할 권한이 없습니다', action: '읽기 전용 토큰으로는 기록을 저장할 수 없습니다. 편집 권한 토큰으로 연결해 주세요.', tone: 'error' },
  NOT_FOUND: { title: '작업 기록을 찾을 수 없습니다', action: '목록을 새로 불러온 뒤 다시 선택해 주세요.', tone: 'error' },
  DATASET_MISMATCH: { title: '프로젝트 생성 이후 자료가 바뀌었습니다', action: '기존 기록은 읽을 수 있지만 새 실행과 근거 조회는 막혀 있습니다. 새 프로젝트로 다시 시작해 주세요.', tone: 'error' },
  INVALID_ARGUMENT: { title: '입력을 확인해 주세요', action: '필수 항목·검토 모델·제품군 범위를 확인해 주세요.', tone: 'error' },
  INVALID_REQUEST: { title: '입력을 확인해 주세요', action: '필수 항목·검토 모델·제품군 범위를 확인해 주세요.', tone: 'error' },
  INVALID_MODEL_ID: { title: '모델을 찾을 수 없습니다', action: '현재 자료에 있는 모델을 선택해 주세요.', tone: 'error' },
  INVALID_DOCUMENT_VERSION: { title: '문서 버전을 찾을 수 없습니다', action: '선택한 모델의 문서 버전을 확인해 주세요.', tone: 'error' },
  CONNECTION_FAILED: { title: '작업실 서버에 연결할 수 없습니다', action: '18869번 작업실 서버가 실행 중인지 확인해 주세요. 저장 요청은 자동으로 다시 보내지 않으니, 목록을 먼저 확인한 뒤 다시 시도해 주세요.', tone: 'error' },
  CONTRACT_MISMATCH: { title: '서버 응답이 공통 규격과 다릅니다', action: '웹과 서버의 계약 버전이 맞는지 PM에게 확인해 주세요.', tone: 'error' },
  NOT_IMPLEMENTED: { title: '요청은 저장됐지만 Agent 분석은 아직 연결되지 않았습니다', action: '후보·대조 결과는 판단 Agent가 연결된 뒤 같은 실행 기록에 표시됩니다.', tone: 'notice' },
};

export function errorView(error: unknown): ErrorView {
  const code = error instanceof ApiError ? error.code : 'UNKNOWN_ERROR';
  const known = ERROR_VIEWS[code];
  if (known) return { code, ...known };
  return { code, title: '요청을 처리하지 못했습니다', action: error instanceof Error ? error.message : '알 수 없는 오류입니다.', tone: 'error' };
}

/** Uses each selected product's registered document version; a missing model is an explicit error, not a default. */
export function documentVersionsFor(products: Product[], modelIds: string[]): Record<string, string> {
  return Object.fromEntries(modelIds.map(id => {
    const version = products.find(product => product.model_id === id)?.document_version;
    if (!version) throw new ApiError('INVALID_MODEL_ID', `${id} 모델의 문서 버전을 찾을 수 없습니다.`);
    return [id, version];
  }));
}

export function projectName(request: PlanningRequest): string {
  const task = request.improvement_task.length > 40 ? `${request.improvement_task.slice(0, 40)}…` : request.improvement_task;
  return `${request.model_ids.join(', ')} · ${task}`;
}

export interface RunStatusView { label: string; detail: string; tone: 'done' | 'notice' | 'error' | 'progress' }

export function runStatusView(status: RunSnapshot['run']['status']): RunStatusView {
  switch (status) {
    case 'completed': return { label: '분석 완료', detail: 'Agent가 판단·검사를 마친 결과입니다.', tone: 'done' };
    case 'held': return { label: '보류', detail: '근거가 부족하거나 확인이 필요해 결과를 보류했습니다.', tone: 'notice' };
    case 'failed': return { label: '실패', detail: '실행 중 오류가 발생했습니다. 미해결 항목을 확인해 주세요.', tone: 'error' };
    case 'not_implemented': return { label: '요청만 저장됨', detail: '판단 Agent가 아직 연결되지 않아 분석을 실행하지 않았습니다.', tone: 'notice' };
    default: return { label: '진행 중', detail: '실행이 끝나지 않았습니다.', tone: 'progress' };
  }
}

export interface EvidenceSearch { query: string; modelId: string; documentVersion: string | null; items: Evidence[]; total: number; method: string }

export function parseEvidenceSearch(data: Record<string, unknown>): EvidenceSearch {
  const search = (data.search as { data: { query: string; model_id: string; document_version: string | null; items: Evidence[]; total: number; search_method: string } }).data;
  return { query: search.query, modelId: search.model_id, documentVersion: search.document_version, items: search.items, total: search.total, method: search.search_method };
}

export const browserFetch: typeof fetch = (input, init) => fetch(input, init);

export type ConnectionState ='disconnected' | 'connecting' | 'connected' | 'error';

export interface LiveWorkspace {
  connection: ConnectionState;
  error: ErrorView | null;
  projects: WorkspaceProject[];
  project: WorkspaceProject | null;
  runs: RunSnapshot[];
  busy: boolean;
  connect: (token: string) => Promise<void>;
  disconnect: () => void;
  selectProject: (id: string) => Promise<void>;
  saveRequest: (request: PlanningRequest, products: Product[]) => Promise<RunSnapshot | null>;
  addRun: (request: PlanningRequest, previousRunId: string | null) => Promise<RunSnapshot | null>;
  search: (query: string, modelId: string) => Promise<EvidenceSearch | null>;
  clearError: () => void;
}

export function useLiveWorkspace(): LiveWorkspace {
  // The token lives in a ref so it never enters rendered state, storage or logs.
  const token = useRef('');
  // WorkspaceClient calls its transport as a method; browsers reject an unbound window.fetch ("Illegal invocation"),
  // so the web passes a wrapper. Node tests did not expose this.
  const client = useRef(new WorkspaceClient('', () => token.current, browserFetch));
  const [connection, setConnection] = useState<ConnectionState>('disconnected');
  const [error, setError] = useState<ErrorView | null>(null);
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [project, setProject] = useState<WorkspaceProject | null>(null);
  const [runs, setRuns] = useState<RunSnapshot[]>([]);
  const [busy, setBusy] = useState(false);

  async function guarded<T>(work: () => Promise<T>): Promise<T | null> {
    setBusy(true); setError(null);
    try { return await work(); } catch (failure) {
      const view = errorView(failure);
      setError(view);
      if (view.code === 'UNAUTHORIZED') setConnection('error');
      return null;
    } finally { setBusy(false); }
  }

  async function loadRuns(projectId: string) {
    const result = await client.current.listRuns(projectId);
    setRuns(result.runs as unknown as RunSnapshot[]);
  }

  return {
    connection, error, projects, project, runs, busy,
    clearError: () => setError(null),
    async connect(value) {
      token.current = value.trim();
      setConnection('connecting');
      const listed = await guarded(() => client.current.listProjects());
      if (!listed) { setConnection('error'); return; }
      setProjects(listed.projects);
      setConnection('connected');
      const latest = listed.projects[listed.projects.length - 1];
      if (latest) { setProject(latest); await guarded(() => loadRuns(latest.project.id)); } else { setProject(null); setRuns([]); }
    },
    disconnect() {
      token.current = '';
      setConnection('disconnected'); setProjects([]); setProject(null); setRuns([]); setError(null);
    },
    async selectProject(id) {
      await guarded(async () => {
        const selected = await client.current.getProject(id);
        setProject(selected);
        await loadRuns(id);
      });
    },
    saveRequest(request, products) {
      return guarded(async () => {
        const created = await client.current.createProject(projectName(request), request as unknown as Record<string, unknown>, documentVersionsFor(products, request.model_ids));
        const run = await client.current.createRun(created.project.id, request as unknown as Record<string, unknown>) as unknown as RunSnapshot;
        setProjects(items => [...items, created]);
        setProject(created);
        setRuns([run]);
        return run;
      });
    },
    addRun(request, previousRunId) {
      return guarded(async () => {
        if (!project) throw new ApiError('NOT_FOUND', '먼저 프로젝트를 선택해 주세요.');
        const run = await client.current.createRun(project.project.id, request as unknown as Record<string, unknown>, previousRunId) as unknown as RunSnapshot;
        setRuns(items => [...items, run]);
        return run;
      });
    },
    search(query, modelId) {
      return guarded(async () => {
        if (!project) throw new ApiError('NOT_FOUND', '먼저 프로젝트를 선택해 주세요.');
        return parseEvidenceSearch(await client.current.search(project.project.id, query, modelId));
      });
    },
  };
}
