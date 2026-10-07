# 15모델 공식 설명서 원본 수령·판본·SHA

기록 ID: `DATA-REMAINING-INTAKE-20261008-01a1100e` · 확인일 2026-10-08 KST.

정확 SKU 지원페이지에서 연결된 15모델/19모델별 PDF 후보를 조사했다. 공개 URL16개를 각각 한 번 받아 HTTP200·PDF 서명·native 표지를 확인했고, 전체 bytes SHA가 서로 다른 원본15개를 보존했다. MWJ25E의 두 URL은 같은 전체 SHA이며, MW20GDN/MW30EDN 및 DUE5BGL1E/DUE5BGE/DFE5BGE는 같은 URL을 공유한다.

원 PDF는 새 local/private 폴더에만 보존한다. PR의 [전체 인계 JSON](manual-acquisition.json), [19행 CSV](manual-reference-table.csv), [발견 당시 후보](manual-link-candidates.json), 아래 표지 및 공식 원본 URL로 다시 받을 수 있다. 재수령한 bytes의 **전체 SHA**가 같아야 같은 원본으로 사용한다. 기존 생산 PDF/238후기/분할/계약/README는 변경하지 않았고 운영에는 등록하지 않았다.

| 모델 | 관측 판본 / 쪽수 | 원 PDF / 표지 | 표지 정확SKU | 적용 상태 |
|---|---|---|---|---|
| [S834MEE111](https://www.lge.co.kr/support/product-S834MEE111) | `MFL71401518 Rev.10_071825` / 36 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=fyN8Fmbfo9ACt8EsWzImmg) · [표지](covers/b22d7ddea163e90a.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [S836MEE022](https://www.lge.co.kr/support/product-S836MEE022) | `MFL71401523 Rev.00_073125` / 36 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=ligy9hfMumSaMBuWNZFGrA) · [표지](covers/cc34f96cf2077c3e.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [T873MEE111](https://www.lge.co.kr/support/product-T873MEE111) | `MFL71401525 Rev.11_091025` / 36 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=a8sdGu0vrerKMqWmu5nkQ) · [표지](covers/e6083d41fe9ea960.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [D502MEE33](https://www.lge.co.kr/support/product-D502MEE33) | `MFL71728032 Rev.00_072723` / 32 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=pu7eIttvUqejungzizJvkQ) · [표지](covers/347ea6c0c06bdd05.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [D502MEE33](https://www.lge.co.kr/support/product-D502MEE33) | `MFL69140210 Rev.00_041421` / 24 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=6kPLmtrN5Bqc2NNcFLjMg) · [표지](covers/e42f2033d335aaab.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [Q405MEE133](https://www.lge.co.kr/support/product-Q405MEE133) | `MFL05784807 Rev.02_092326` / 36 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=sSCmA5uf87A2wNlbpMmKkA) · [표지](covers/cc3a1470409bfb6a.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [MW20GDN](https://www.lge.co.kr/support/product-MW20GDN) | `MFL71975601 Rev.06_031126` / 36 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=YvbEzv4uUqAGHWDgT7CA) · [표지](covers/743444a78daeca56.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MW30EDN](https://www.lge.co.kr/support/product-MW30EDN) | `MFL71975601 Rev.06_031126` / 36 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=YvbEzv4uUqAGHWDgT7CA) · [표지](covers/743444a78daeca56.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MW25B](https://www.lge.co.kr/support/product-MW25B) | `MFL68822520 Rev.22_090525` / 44 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=4sC92FxavmzZ2zqt4S0YoQ) · [표지](covers/e558ec0e4f00af2f.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MW25B](https://www.lge.co.kr/support/product-MW25B) | `MFL68822540 Rev.00_040826` / 44 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=hsYsF0eIFyeDgjPrRrt6lA) · [표지](covers/1057211db93d4491.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MWJ25E](https://www.lge.co.kr/support/product-MWJ25E) | `MFL68822525 Rev.07_090525` / 44 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=mEn7jHmMdCixmSM2xLC8oA) · [표지](covers/430ae616fa6d1463.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MWJ25E](https://www.lge.co.kr/support/product-MWJ25E) | `MFL68822525 Rev.07_090525` / 44 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=CzsKp81ypV4rWj7oxpqRBw) · [표지](covers/430ae616fa6d1463.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MWE25HD](https://www.lge.co.kr/support/product-MWE25HD) | `MFL68822533 Rev.01_121125` / 44 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=DzS5uYbHlIlI53Kq5DEwLg) · [표지](covers/93fef8f94586b329.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [MWE25HD](https://www.lge.co.kr/support/product-MWE25HD) | `MFL68822533 Rev.02_030326` / 44 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=dK5FlSmySSzQBa7TIXBuIQ) · [표지](covers/4ccc7fbd2a753c05.png) | 명시 | reference만 확보·전체기능/구매시점판 미확인 |
| [DUE4BGL1E](https://www.lge.co.kr/support/product-DUE4BGL1E) | `MFL71959121 Rev.02_031826` / 56 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=Y17h92wAr7LT7sBV2Mxqwg) · [표지](covers/d7b659a628c7e699.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [DUE1BGL1E](https://www.lge.co.kr/support/product-DUE1BGL1E) | `MFL71959119 Rev.06_031926` / 56 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=LZAq0EEc3md9sgrA2iSmA) · [표지](covers/e2ac97d7ed5c9614.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [DUE5BGL1E](https://www.lge.co.kr/support/product-DUE5BGL1E) | `MFL71959118 Rev.08_030626` / 56 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=PcDVhXACRZY2uBxQHWYECQ) · [표지](covers/e16f0b79c414b783.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [DUE5BGE](https://www.lge.co.kr/support/product-DUE5BGE) | `MFL71959118 Rev.08_030626` / 56 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=PcDVhXACRZY2uBxQHWYECQ) · [표지](covers/e16f0b79c414b783.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |
| [DFE5BGE](https://www.lge.co.kr/support/product-DFE5BGE) | `MFL71959118 Rev.08_030626` / 56 | [공식 PDF](https://gscs-b2c.lge.com/open/downloadFile?fileId=PcDVhXACRZY2uBxQHWYECQ) · [표지](covers/e16f0b79c414b783.png) | 공용/패턴 | reference만 확보·전체기능/구매시점판 미확인 |

## 모델·판본을 섞지 않는 기준

- 표지에 정확 SKU를 직접 확인한 모델은 MW20GDN·MW30EDN·MW25B·MWJ25E·MWE25HD의 5개다. 이는 모델별 기능·코스·설치구성 전부를 승인한 결과가 아니다.
- 나머지10모델은 정확 SKU 지원페이지 링크는 확인했지만 표지에 SKU가 직접 명시되지 않거나 공용 모델 패턴이다. 지원페이지 연결만으로 모든 기능·수치가 동일하다고 판단하지 않는다.
- MW25B의 MFL68822520 Rev.22_090525와 MFL68822540 Rev.00_040826, MWE25HD의 같은 MFL68822533 Rev.01_121125/Rev.02_030326, D502MEE33의 두 문서는 각각 별도 SHA로 유지한다. 등록일이 늦다는 이유로 기존 원문을 교체하지 않는다.
- 공용 DUE5/DFE5 PDF에서는 빌트인/프리스탠딩 및 개별 기능 적용을 추가로 대조해야 한다. 정확 구매SKU와 구매시점판은 전15모델 미확인이다.
- PDP 팝업의 F19WDLP/SC5MBR62B 또는 중앙 선택 UI의 OLED/Windows11 예시는 선택된 주방 SKU의 설명서로 인정하지 않았다. 이번 확보는 모델별 지원페이지의 실제 공개 PDF 링크를 사용했다.
- 지원목록의 등록일·PDF Rev 표기·FAQ 표시일·고객 후기 게시일은 서로 다른 필드다. PDF 표지를 읽는 native extraction16회 외에 OCR/모델 실행은0이다.

## 다음 인수

PM과 D2 담당자는 공개 URL·전체 SHA·판본·공용 적용 제한을 확인한 다음 필요한 모델/구간의 등록 여부를 결정한다. 이 참고팩은 생산팩 또는 승인된 Evidence를 대신하지 않는다. 원 리뷰 ID/게시일 필드/실사용·중복 계보는 [Q&A·후기 후보](qa-review-candidates.md)에서 별도로 인계한다.
