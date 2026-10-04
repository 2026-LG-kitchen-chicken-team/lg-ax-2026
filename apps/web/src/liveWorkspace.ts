/** Live-mode connection to the authenticated workspace API (P2-WEB-002); credential stays in React memory only. */
import { useEffect, useRef, useState } from 'react';
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
  INVALID_EVIDENCE_ID: { title: '근거 원문을 찾을 수 없습니다', action: '인용된 근거 ID가 현재 자료에 없습니다. 자료 버전과 근거 ID를 확인해 주세요.', tone: 'error' },
  VALIDATION_FAILED: { title: '검사를 통과하지 못했습니다', action: '인용 누락·모델 혼동·기능 중복 검사에서 실패했습니다. 미해결 항목과 수정 기록을 확인해 주세요.', tone: 'error' },
  INSUFFICIENT_EVIDENCE: { title: '근거가 부족해 보류했습니다', action: '후보를 억지로 만들지 않았습니다. 자료를 보강하거나 검토 조건을 바꿔 다시 요청해 주세요.', tone: 'notice' },
  MODEL_UNAVAILABLE: { title: '분석 모델을 사용할 수 없습니다', action: '모델 서버 연결 또는 응답 형식에 문제가 있습니다. 잠시 후 다시 시도하거나 PM에게 모델 상태를 확인해 주세요.', tone: 'error' },
};

/** A changed request on the same product group and model set continues the project; otherwise it starts a new one. */
export function sameProjectScope(project: PlanningRequest, request: PlanningRequest): boolean {
  const models = (ids: string[]) => [...ids].sort().join('\n');
  return project.product_group === request.product_group && models(project.model_ids) === models(request.model_ids);
}

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
  scopeVersion: number;
  connect: (token: string) => Promise<void>;
  disconnect: () => void;
  selectProject: (id: string) => Promise<void>;
  saveRequest: (request: PlanningRequest, products: Product[]) => Promise<RunSnapshot | null>;
  addRun: (request: PlanningRequest, previousRunId: string | null) => Promise<RunSnapshot | null>;
  search: (query: string, modelId: string) => Promise<EvidenceSearch | null>;
  clearError: () => void;
}

export function useLiveWorkspace(): LiveWorkspace {
  // Each client captures one credential. A delayed operation cannot switch to a new login's token.
  const client = useRef<WorkspaceClient | null>(null);
  const selectedProject = useRef<WorkspaceProject | null>(null);
  const connected = useRef(false);
  const generation = useRef(0);
  const pending = useRef(0);
  const [state, setState] = useState({
    connection: 'disconnected' as ConnectionState, error: null as ErrorView | null,
    projects: [] as WorkspaceProject[], project: null as WorkspaceProject | null,
    runs: [] as RunSnapshot[], busy: false, scopeVersion: 0,
  });

  useEffect(() => () => {
    generation.current += 1;
    pending.current = 0;
    connected.current = false;
    client.current = null;
    selectedProject.current = null;
  }, []);

  function newScope(): number {
    const scope = ++generation.current;
    pending.current = 0;
    selectedProject.current = null;
    setState(value => ({ ...value, project: null, runs: [], busy: false, error: null, scopeVersion: scope }));
    return scope;
  }

  async function guarded<T>(work: (api: WorkspaceClient, current: () => boolean) => Promise<T>, scope = generation.current): Promise<T | null> {
    const api = client.current;
    const current = () => scope === generation.current;
    pending.current += 1;
    setState(value => ({ ...value, busy: true, error: null }));
    try {
      if (!api) throw new ApiError('UNAUTHORIZED', '작업실 인증이 필요합니다.');
      const result = await work(api, current);
      return current() ? result : null;
    } catch (failure) {
      if (!current()) return null;
      const view = errorView(failure);
      if (view.code === 'UNAUTHORIZED') {
        newScope();
        connected.current = false;
        client.current = null;
        setState(value => ({ ...value, connection: 'error', projects: [], error: view }));
      } else setState(value => ({ ...value, error: view }));
      return null;
    } finally {
      if (current()) {
        pending.current -= 1;
        setState(value => ({ ...value, busy: pending.current > 0 }));
      }
    }
  }

  function requireProject(): WorkspaceProject {
    if (!connected.current) throw new ApiError('UNAUTHORIZED', '작업실 인증이 필요합니다.');
    if (!selectedProject.current) throw new ApiError('NOT_FOUND', '먼저 프로젝트를 선택해 주세요.');
    return selectedProject.current;
  }

  function applyProject(project: WorkspaceProject, runs: RunSnapshot[]): void {
    if (runs.some(item => item.run.project_id !== project.project.id)) {
      throw new ApiError('CONTRACT_MISMATCH', '선택한 프로젝트와 실행 기록의 범위가 다릅니다.');
    }
    selectedProject.current = project;
    setState(value => ({ ...value, project, runs }));
  }

  return {
    ...state,
    clearError: () => setState(value => ({ ...value, error: null })),
    async connect(value) {
      const scope = newScope();
      const credential = value.trim();
      connected.current = false;
      client.current = new WorkspaceClient('', () => credential, browserFetch);
      setState(previous => ({ ...previous, connection: 'connecting', projects: [] }));
      const result = await guarded(async (api, current) => {
        const listed = await api.listProjects();
        if (!current()) return false;
        const latest = listed.projects[listed.projects.length - 1];
        const runs = latest ? (await api.listRuns(latest.project.id)).runs as unknown as RunSnapshot[] : [];
        if (!current()) return false;
        if (latest) applyProject(latest, runs);
        connected.current = true;
        setState(previous => ({ ...previous, connection: 'connected', projects: listed.projects }));
        return true;
      }, scope);
      if (!result && scope === generation.current) {
        connected.current = false;
        client.current = null;
        setState(previous => ({ ...previous, connection: 'error', projects: [], project: null, runs: [] }));
      }
    },
    disconnect() {
      newScope();
      connected.current = false;
      client.current = null;
      setState(value => ({ ...value, connection: 'disconnected', projects: [] }));
    },
    async selectProject(id) {
      const scope = newScope();
      await guarded(async (api, current) => {
        if (!connected.current) throw new ApiError('UNAUTHORIZED', '작업실 인증이 필요합니다.');
        const [project, listed] = await Promise.all([api.getProject(id), api.listRuns(id)]);
        if (!current()) return;
        applyProject(project, listed.runs as unknown as RunSnapshot[]);
      }, scope);
    },
    saveRequest(request, products) {
      const scope = newScope();
      return guarded(async (api, current) => {
        if (!connected.current) throw new ApiError('UNAUTHORIZED', '작업실 인증이 필요합니다.');
        const created = await api.createProject(projectName(request), request as unknown as Record<string, unknown>, documentVersionsFor(products, request.model_ids));
        if (!current()) return null;
        setState(value => ({ ...value, projects: [...value.projects, created] }));
        const run = await api.createRun(created.project.id, request as unknown as Record<string, unknown>) as unknown as RunSnapshot;
        if (!current()) return null;
        applyProject(created, [run]);
        return run;
      }, scope);
    },
    addRun(request, previousRunId) {
      return guarded(async (api, current) => {
        const project = requireProject();
        const run = await api.createRun(project.project.id, request as unknown as Record<string, unknown>, previousRunId) as unknown as RunSnapshot;
        if (!current()) return null;
        if (run.run.project_id !== project.project.id) throw new ApiError('CONTRACT_MISMATCH', '실행 기록의 프로젝트 범위가 다릅니다.');
        setState(value => ({ ...value, runs: [...value.runs, run] }));
        return run;
      });
    },
    search(query, modelId) {
      return guarded(async (api, current) => {
        const project = requireProject();
        if (!(modelId in project.document_versions)) throw new ApiError('INVALID_ARGUMENT', '선택한 모델은 프로젝트 검토 범위가 아닙니다.');
        const payload = await api.search(project.project.id, query, modelId);
        if (!current()) return null;
        const result = parseEvidenceSearch(payload);
        if (payload.project_id !== project.project.id || payload.dataset_sha256 !== project.dataset_sha256
          || result.modelId !== modelId || result.documentVersion !== project.document_versions[modelId]) {
          throw new ApiError('CONTRACT_MISMATCH', '근거 검색 결과의 프로젝트·모델·문서 범위가 다릅니다.');
        }
        return result;
      });
    },
  };
}
