# KITCHEN AX approved UI composition — 2026-10-17

The user selected the first attachment for the seated researchers and workrooms, and the second attachment for the laboratory page composition. This change modifies presentation only.

## Original image

- Workspace asset: public/workshops/approved-researchers-original-v1.png
- SHA-256: 2afa9bbf0965b93a05e8b3f70e5afc4f538eeb15ad21b49ea040c6412daac1af
- This file is an exact binary copy of the approved attachment, with no pixel editing, recoloring, regeneration or background removal. Display geometry selects the six room regions and clips the outer white margin.
- Empty-room and existing motion images remain unchanged. They are reused for the existing execution animation. No new character artwork was generated in this change.

## Composition

The six rooms keep their numbered order around a central planner console. A warm ivory window wall, shared floor, front fascia names and compact existing controls follow the selected page reference. Room addresses remain fixed across Skill activation; existing state-derived parallel scales are reused. Mobile uses the existing two-column reflow and on-demand detail sheet.

## Functional boundary

The public baseline is 8eebfa2f66a15f6159e3d477771a234d5937af51. Its existing execution, pipeline, observer, storage and replay code is unchanged. Forty-one existing non-renderer source/style files were compared with that baseline; no differences were found. The new presentation modules do not create jobs, skills, model calls, progress or logs.

## Validation

- 143 JavaScript tests passed, including original-image hash, fixed room addresses, existing parallel scales and complete camera bounds.
- Vite production build passed.
- Browser checks: desktop, phone, idle state, room selection, right detail panel, close/Escape return and 3/6-room explicit motion previews.
- Existing researchers and role-specific animation timing were retained. Redesigning their work actions is outside this UI change.
