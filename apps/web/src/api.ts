import Ajv2020 from 'ajv/dist/2020';
import schema from '../../../packages/contracts/schemas/lgax.schema.json';
import type { BootstrapData } from './domain';

const ajv = new Ajv2020({ allErrors: true, strict: false });
ajv.addSchema(schema, 'lgax');
const validateBootstrap = ajv.compile({ $ref: 'lgax#/$defs/WorkspaceBootstrapResponse' });
const validatePlanningRequest = ajv.compile({ $ref: 'lgax#/$defs/PlanningRequest' });

export class ApiError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

export function parseBootstrap(payload: unknown): BootstrapData {
  if (!validateBootstrap(payload)) {
    const details = validateBootstrap.errors?.map(error => `${error.instancePath || '/'} ${error.message}`).join('; ');
    throw new ApiError('CONTRACT_MISMATCH', `공통 데이터 규격과 응답이 일치하지 않습니다. ${details ?? ''}`);
  }
  return (payload as { ok: true; data: BootstrapData }).data;
}

export async function loadBootstrap(signal?: AbortSignal): Promise<BootstrapData> {
  let response: Response;
  try {
    response = await fetch('/api/bootstrap', { signal });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new ApiError('API_UNAVAILABLE', '공통 API에 연결할 수 없습니다. 18867번 서버가 실행 중인지 확인해 주세요.');
  }
  if (!response.ok) throw new ApiError('API_ERROR', `공통 API가 HTTP ${response.status} 응답을 반환했습니다.`);
  try {
    return parseBootstrap(await response.json());
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('INVALID_JSON', '공통 API 응답을 JSON으로 읽을 수 없습니다.');
  }
}

export async function requestPlanning(payload: Record<string, unknown>): Promise<void> {
  if (!validatePlanningRequest(payload)) {
    throw new ApiError('INVALID_REQUEST', `기획 요청의 입력을 확인해 주세요. ${ajv.errorsText(validatePlanningRequest.errors)}`);
  }
  let response: Response;
  try {
    response = await fetch('/api/planning-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError('API_UNAVAILABLE', '공통 API에 연결할 수 없습니다. 서버 연결을 확인해 주세요.');
  }
  const body: unknown = await response.json().catch(() => null);
  if (body && typeof body === 'object' && 'error' in body) {
    const error = body.error;
    if (error && typeof error === 'object' && 'code' in error && 'message' in error) {
      throw new ApiError(String(error.code), String(error.message));
    }
  }
  if (!response.ok) throw new ApiError('API_ERROR', `기획 요청에 HTTP ${response.status} 오류가 발생했습니다.`);
  throw new ApiError('NOT_IMPLEMENTED', '기획 Agent 실행은 아직 연결되지 않았습니다. 현재는 자료 조회와 요청 입력까지만 사용할 수 있습니다.');
}
