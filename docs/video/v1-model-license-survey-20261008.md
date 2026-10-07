# V1 영상 제작용 오픈 웨이트 모델 라이선스 조사 (2026-10-08)

담당: 최길웅(WEB) · 배정: [#239](https://github.com/2026-LG-kitchen-chicken-team/lg-ax-2026/issues/239) · 관련 문서: [V1 1단계 스토리보드](v1-concept-storyboard-20261008.md) · 기록: [최길웅-20261008-063](../작업기록/최길웅/2026-10-08/최길웅-20261008-063.md)

- **용도:** PM이 V1 2단계(참조 이미지 → 장면 영상 → 한국어 내레이션)에 쓸 모델을 정할 때 참고할 자료다. 모델을 실행하거나 내려받지 않았다. 사용을 결정한 것도 아니다.
- **조사 방법:** 조사 에이전트(Claude 하위 에이전트)가 Hugging Face 모델 카드·LICENSE 파일, 공식 GitHub, 공식 라이선스 페이지만 확인했다(확인일 2026-10-08).
  - 페이지는 요약 도구를 거쳐 읽었다. **최종 법적 판단 전에는 각 원문을 사람이 다시 읽어야 한다.**
  - 해커톤 제출 영상이 '상업적 사용'에 해당하는지는 법적 판단이라 정하지 않았다. 상업적 사용으로 보더라도 안전한 쪽을 따로 표시했다.

## 1. 텍스트→이미지(참조 이미지)
| 모델 | 라이선스 | 상업적 사용 | 조건·제한 | VRAM(공식) |
|---|---|---|---|---|
| black-forest-labs/FLUX.1-schnell | Apache-2.0 | 허용 | 카드의 금지 용도(불법·착취·허위정보·비동의 성적 콘텐츠) | 공식 미기재 |
| black-forest-labs/FLUX.1-dev | FLUX.1 [dev] Non-Commercial | 모델은 비상업만, 산출물은 상업 가능 | 수익 활동·"최종 사용자에게 영향" 사용 금지, 동의 후 접근 | 공식 미기재 |
| stabilityai/stable-diffusion-3.5-large / -medium | Stability Community License | 연매출 100만 달러 미만이면 허용 | 상업 사용 시 Stability 등록과 "Powered by Stability AI" 표기, AUP | 공식 미기재 |
| stabilityai/stable-diffusion-xl-base-1.0 | CreativeML Open RAIL++-M | 허용 | 부속서 A 사용 제한을 하위 사용자에게도 적용 | 공식 미기재 |

## 2. 이미지→영상 / 텍스트→영상
| 모델 | 라이선스 | 상업적 사용 | 조건·제한 | VRAM(공식) |
|---|---|---|---|---|
| Wan-AI/Wan2.1(T2V-1.3B, I2V-14B) | Apache-2.0 | 허용 | 위법·해악 콘텐츠 책임은 사용자 | T2V-1.3B 8.19GB, I2V-14B 미기재 |
| Wan-AI/Wan2.2(TI2V-5B, A14B) | Apache-2.0 | 허용 | 위와 같음 | TI2V-5B 24GB 이상(offload), A14B 80GB 이상 |
| tencent/HunyuanVideo, HunyuanVideo-1.5 | Tencent Hunyuan Community | **한국에서 사용 불가** | 적용 지역에서 EU·영국·한국을 제외 | 원본 45~80GB, 1.5는 14GB(offload) |
| Lightricks/LTX-Video, LTX-2 | LTX Open-Weights / LTX-2 Community | 연매출 1,000만 달러 미만이면 무료 | AI 생성 고지 의무, 딥페이크 금지 | 공식 미기재 |
| zai-org/CogVideoX-2b | Apache-2.0 | 허용 | 없음 | FP16 4GB부터(최적화 시) |
| zai-org/CogVideoX-5b(I2V 포함) | CogVideoX LICENSE | 등록 후에만 허용 | 상업 라이선스 등록, 월 방문 100만 이하, 군사 용도 등 금지 | BF16 5GB부터(최적화 시) |

## 3. 한국어 TTS(내레이션)
| 모델 | 라이선스 | 상업적 사용 | 조건·제한 | 한국어 | VRAM(공식) |
|---|---|---|---|---|---|
| myshell-ai/MeloTTS-Korean | MIT | 허용 | 없음 | 지원(`KR`) | 공식 미기재(CPU 실시간 가능 표기) |
| coqui/XTTS-v2 | Coqui Public Model License 1.0.0 | **불가(산출물 포함)** | 대가가 생기면 비상업 범위를 벗어남 | 지원 | 공식 미기재 |
| Supertone/supertonic-2 | 모델 OpenRAIL-M, 코드 MIT | 허용 | 기계 생성 고지, 사칭·딥페이크 금지 | 지원 | 공식 미기재 |

## 4. 정리
- **상업적 사용으로 보더라도 조건 없이 쓸 수 있는 것(Apache-2.0/MIT):** FLUX.1-schnell, Wan2.1, Wan2.2, CogVideoX-2b, MeloTTS-Korean
- **조건을 지키면 쓸 수 있는 것:** LTX-Video·LTX-2·SDXL·Supertonic-2. 사용 제한을 지키고 AI 생성임을 고지해야 한다.
- **별도 절차가 필요한 것:** SD3.5는 등록과 표기, CogVideoX-5b는 상업 라이선스 등록이 필요하다.
- **피할 것:** HunyuanVideo 전 계열(한국 제외), XTTS-v2(비상업만), FLUX.1-dev(모델 비상업, 조항 모호)
- **장비:** 연구실 GPU를 쓸 경우, 기존 규칙대로 사용량·프로세스·저장 공간을 먼저 확인한다. 큰 모델(Wan2.2 A14B 80GB 등)은 실행 전 여유를 확인해야 한다.

## 5. 확인하지 못한 것
- '공식 미기재'로 둔 VRAM 값(블로그 수치는 쓰지 않았다)
- LTX-Video 0.9~0.9.5 개별 라이선스 본문, LTX-2.3 사양
- coqui.ai/cpml 페이지(404, HF LICENSE.txt로 대신 확인)
- Stability AUP 전문, Wan2.2 A14B 개별 LICENSE 파일(README 기준 Apache-2.0)
- CogVideoX-5b-I2V 저장소 페이지
- 영상 모델의 한국어 프롬프트 이해도, MeloTTS 한국어 화자 수
- 대회 규정상 생성형 영상 사용 가능 여부와 제출 영상 길이
