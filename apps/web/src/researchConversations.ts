import type { PlanningBrief } from './research';

/** Only validated briefs in this connection and bundle can form a conversation. */
export function conversationPath(history: PlanningBrief[], selected: PlanningBrief): PlanningBrief[] {
  const byId = new Map(history.filter(item => item.bundle_id === selected.bundle_id).map(item => [item.brief_id, item]));
  const path: PlanningBrief[] = [];
  const visited = new Set<string>();
  let current: PlanningBrief | undefined = selected;
  while (current && !visited.has(current.brief_id)) {
    visited.add(current.brief_id);
    path.unshift(current);
    current = current.previous_brief_id ? byId.get(current.previous_brief_id) : undefined;
  }
  return path;
}

export function conversationThreads(history: PlanningBrief[]): PlanningBrief[] {
  const latest = new Map<string, PlanningBrief>();
  for (const brief of history) {
    const root = conversationPath(history, brief)[0];
    latest.set(`${brief.bundle_id}:${root.previous_brief_id ?? root.brief_id}`, brief);
  }
  return [...latest.values()].reverse();
}
