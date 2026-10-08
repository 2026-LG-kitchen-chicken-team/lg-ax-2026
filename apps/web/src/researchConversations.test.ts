import { describe, expect, it } from 'vitest';
import { heldBrief } from './fixtures/research-test-data';
import { conversationPath, conversationThreads } from './researchConversations';

describe('planning conversations follow explicit saved revision links', () => {
  const first = heldBrief();
  const next = { ...first, brief_id: 'next', run_id: 'next-run', revision: 1, previous_brief_id: first.brief_id };
  it('groups revisions while retaining an independent new planning conversation', () => {
    const separate = { ...first, brief_id: 'separate', run_id: 'separate-run' };
    expect(conversationPath([first, next, separate], next)).toEqual([first, next]);
    expect(conversationThreads([first, next, separate])).toEqual([separate, next]);
  });
  it('never joins a different bundle through an overlapping brief ID', () => {
    const other = { ...first, bundle_id: 'another-bundle' };
    expect(conversationPath([other, next], next)).toEqual([next]);
    expect(conversationThreads([other, next])).toHaveLength(2);
  });
  it('bounds a corrupt cyclic lineage and shows a recovered revision without invented parents', () => {
    const cyclic = { ...first, previous_brief_id: next.brief_id };
    expect(conversationPath([cyclic, next], next)).toHaveLength(2);
    expect(conversationPath([next], next)).toEqual([next]);
  });
});
