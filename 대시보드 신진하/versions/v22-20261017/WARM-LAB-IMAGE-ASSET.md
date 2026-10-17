# 생성 이미지로 보완한 연구소 환경

- 사용 모드: 내장 ImageGen, 참고 이미지 기반 생성. API/CLI 우회 사용 없음.
- 자산: `public/environment/warm-research-wall-v1.png`, 2172×724, 불투명 PNG.
- 생성 원본은 기본 생성 폴더에 유지하고 소비하는 사본을 프로젝트에 추가했습니다.
- 3D 벽면에 실제 텍스처로 적용하며, 작업실·연구원·클릭·현재 실행 상태는 기존 실시간 코드가 그립니다.
- 이미지는 장식용 건축/수납/창가이며 실제 업무 자료나 실행 증거가 아닙니다.

## 최종 프롬프트

```text
Use case: stylized-concept.
Asset type: production architectural wall texture for the back wall of a real-time miniature 3D kitchen product research laboratory, not a UI mockup.
Reference image: supplied KITCHEN AX screenshot ONLY as palette/material/miniature-render style reference. Do not reproduce its UI, people, floating work platforms, connecting bridges, lettering, or empty floor.
Create a richly detailed, warm premium product design laboratory wall, straight-on front elevation, perfectly level horizontal camera, orthographic, very wide landscape panoramic composition about 3:1. Fill the entire image with the wall elevation. Bottom 35 percent: a continuous run of low light-oak and muted sage cabinets, inset drawers with tiny brushed brass pulls, cream solid-surface countertop, tidy document binders, small product material samples, ceramic mugs, paper trays, a few broad-leaf potted plants, a clean small appliance prototype. Upper 65 percent: tall elegant sage-framed windows revealing a lush leafy courtyard with soft morning light, some slim oak shelves with neatly arranged folders and plants; off-white plaster, oak slat accents, small warm under-shelf task lights. Everything belongs to one coherent believable research laboratory. Contemporary architectural visualization rendered as refined miniature 3D, physically grounded, delicate contact shadows, tactile wood grain, soft depth. Palette ivory #f6f0e3, muted sage #6f826d, pale oak #cbb48b, restrained warm brass. Much richer and more purposeful than a bare tiled floor. No people, no robots, no words, no logos, no charts showing fake metrics, no labels, no UI, no border, no top-down floor, no central empty room. Opaque image.
```
