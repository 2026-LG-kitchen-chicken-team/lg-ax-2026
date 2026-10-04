/**
 * E03 planner modification time (P2-WEB-004). Follows docs/pm/evaluation.md: the same goal and explicit start/end rules
 * are recorded with each value, unmeasured time stays null, and 0 appears only when actually measured as 0.
 * The web measures elapsed screen time; it does not claim any efficiency gain.
 */
import { ApiError } from './api';
import type { CandidateChoice, DataMode } from './planning';

export const START_RULE = '기획자가 수정 목표를 적고 "측정 시작"을 누른 시각';
export const END_RULE = '조건·후보를 고친 재실행 요청이 저장(fixture는 초안 생성)된 시각';

export interface EditSummary { candidates_changed: number; conditions_added: number; conditions_removed: number }

/** A browser scope identifier contains no token and is renewed when the workspace connection or project changes. */
export interface MeasurementScope { scope_id: string; project_id: string; project_owner_id: string | null }
export interface MeasurementCompletion { mode: DataMode; base_run_id: string; scope: MeasurementScope }

export interface ModificationMeasurement {
  measurement_id: string;
  goal: string;
  mode: DataMode;
  execution_kind: 'fixture_browser' | 'live_service';
  participant_kind: 'unconfirmed';
  scope: MeasurementScope | null;
  base_run_id: string;
  result_run_id: string | null;
  started_at: string;
  ended_at: string | null;
  status: 'running' | 'completed' | 'cancelled';
  modification_seconds: number | null;
  edits: EditSummary | null;
}

export function startMeasurement(goal: string, baseRunId: string, mode: DataMode, id: string, now: Date, scope: MeasurementScope | null = null): ModificationMeasurement {
  const text = goal.trim();
  if (!text) throw new ApiError('INVALID_ARGUMENT', '측정할 수정 목표를 적어 주세요. 같은 목표끼리만 시간을 비교할 수 있습니다.');
  return { measurement_id: id, goal: text, mode, execution_kind: mode === 'fixture' ? 'fixture_browser' : 'live_service', participant_kind: 'unconfirmed', scope: scope ? { ...scope } : null,
    base_run_id: baseRunId, result_run_id: null, started_at: now.toISOString(), ended_at: null, status: 'running', modification_seconds: null, edits: null };
}

export function finishMeasurement(measurement: ModificationMeasurement, resultRunId: string, edits: EditSummary, now: Date, completion?: MeasurementCompletion): ModificationMeasurement {
  if (measurement.status !== 'running') throw new ApiError('INVALID_ARGUMENT', '진행 중인 측정이 아닙니다.');
  if (measurement.scope && (!completion || completion.mode !== measurement.mode || completion.base_run_id !== measurement.base_run_id
    || completion.scope.scope_id !== measurement.scope.scope_id || completion.scope.project_id !== measurement.scope.project_id
    || completion.scope.project_owner_id !== measurement.scope.project_owner_id)) {
    throw new ApiError('INVALID_ARGUMENT', '측정 시작 이후 작업 범위나 기준 실행이 바뀌었습니다.');
  }
  const seconds = (now.getTime() - Date.parse(measurement.started_at)) / 1000;
  if (!Number.isFinite(seconds) || seconds < 0) throw new ApiError('INVALID_ARGUMENT', '측정 시각이 올바르지 않습니다.');
  // Preserve the measured milliseconds: rounding a positive short interval to zero fabricates a zero measurement.
  return { ...measurement, status: 'completed', result_run_id: resultRunId, ended_at: now.toISOString(), modification_seconds: seconds, edits };
}

/** A cancelled or interrupted attempt keeps its record but has no time: null, never 0. */
export function cancelMeasurement(measurement: ModificationMeasurement, now: Date): ModificationMeasurement {
  return { ...measurement, status: 'cancelled', ended_at: now.toISOString(), modification_seconds: null };
}

export function editSummary(beforeChoices: Record<string, CandidateChoice>, afterChoices: Record<string, CandidateChoice>, beforeConditions: string[], afterConditions: string[]): EditSummary {
  const ids = new Set([...Object.keys(beforeChoices), ...Object.keys(afterChoices)]);
  return {
    candidates_changed: [...ids].filter(id => (beforeChoices[id] ?? 'keep') !== (afterChoices[id] ?? 'keep')).length,
    conditions_added: afterConditions.filter(item => !beforeConditions.includes(item)).length,
    conditions_removed: beforeConditions.filter(item => !afterConditions.includes(item)).length,
  };
}

export interface MeasurementExport {
  schema_version: 1;
  generated_at: string;
  notice: string;
  rules: { start: string; end: string; unit: 'seconds'; unmeasured: 'null' };
  records: ModificationMeasurement[];
}

export function exportMeasurements(records: ModificationMeasurement[], generatedAt: string): MeasurementExport {
  return {
    schema_version: 1, generated_at: generatedAt,
    notice: '브라우저 시계로 잰 수정 요청 저장 시간이다. fixture는 브라우저 초안, live는 작업실 요청 저장이며 Agent 실행 완료 시간은 아니다. 사람의 조작인지 자동화인지 확인하지 않았으므로 별도 평가 근거가 필요하다. 같은 수정 목표끼리만 비교하며, 취소·미완료는 null이다. 이 기록만으로 시간 절감 효과를 주장하지 않는다.',
    rules: { start: START_RULE, end: END_RULE, unit: 'seconds', unmeasured: 'null' },
    records,
  };
}
