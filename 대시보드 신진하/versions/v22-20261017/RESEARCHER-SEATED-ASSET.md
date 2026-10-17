# 대기 연구원 이미지

- 생성 모드: 기본 내장 ImageGen, 참조 이미지 기반 편집, 투명 배경.
- 최종 자산: `public/characters/researcher-seated-v1.png` (1536×1024 RGBA).
- 기존 서기·작업·걷기 원본은 보존했습니다. 대기는 한 명의 정적인 앉은 캐릭터이며 실제 Agent 수를 뜻하지 않습니다.
- 기준 프롬프트:

```text
Use case: identity-preserve
Asset type: transparent seated researcher sprite atlas for the existing KITCHEN AX miniature lab.
Reference image: public/characters/researcher-team-v1.png; retain the six existing faces, hair, clothing and 3D render style.
Primary request: exactly six matching human researchers seated naturally in muted sage office swivel chairs, in a strict 3-column by 2-row atlas, one complete seated figure and chair per equal cell.
Top row: wavy-haired young man without glasses; bob-haired woman with round glasses; side-parted man without glasses.
Bottom row: ponytail woman without glasses; short-curly-haired man without glasses; bun-haired woman with round glasses.
Preserve white lab coats, sage shirts, charcoal trousers, white/sage shoes and orange lanyards. Front three-quarter slightly elevated isometric view facing right; hips on cushion, bent knees, feet planted, hands relaxed in lap or on a closed tablet.
Composition: equal scale, consistent feet baseline, generous transparent padding in every cell. Entire chair and shoes visible.
Avoid: desks, monitors, labels, grid lines, extra people, standing legs, floor plane, background gradients. Preserve original character identities.
Output: true transparent RGBA background.
```
