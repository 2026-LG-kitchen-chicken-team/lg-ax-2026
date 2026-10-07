"""Build reviewable metadata/covers from existing private captures; no HTTP/OCR."""

import csv
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
REF = ROOT / "data/reference/data-remaining-intake/20261008-01a1100e"
PRIVATE = ROOT / "private/data-remaining-intake/20261008-01a1100e/manuals"


def main():
    path = REF / "manual-acquisition.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    candidates = [c for row in result["models"] for c in row["candidates"]]
    by_url = {c["url"]: c for c in candidates}
    by_sha = {c["pdf_sha256"]: c for c in candidates if c["pdf_sha256"]}
    result.pop("unique_PDF_captures", None)  # Initial capture counted unique URLs.
    result["public_URL_PDF_captures"] = len([c for c in by_url.values() if c["pdf_sha256"]])
    result["unique_PDF_content_SHA_count"] = len(by_sha)
    (REF / "covers").mkdir(exist_ok=True)
    for c in by_sha.values():
        captured = ROOT / c["local_private_path"]
        if hashlib.sha256(captured.read_bytes()).hexdigest() != c["pdf_sha256"]:
            raise ValueError("Captured original PDF changed")
        cover = captured.with_suffix(".cover.png").read_bytes()
        file = REF / "covers" / (c["pdf_sha256"][:16] + ".png")
        if file.exists() and file.read_bytes() != cover:
            raise ValueError("Existing new-folder cover changed")
        if not file.exists():
            file.write_bytes(cover)
    rows = []
    for model in result["models"]:
        for c in model["candidates"]:
            versions = [re.sub(r"\s+", " ", v).strip() for v in c["cover_versions"]]
            c["observed_cover_versions_normalized"] = versions
            c["reference_cover_path"] = "covers/" + c["pdf_sha256"][:16] + ".png"
            cover = REF / c["reference_cover_path"]
            c["reference_cover_sha256"] = hashlib.sha256(cover.read_bytes()).hexdigest()
            rows.append({"model_id": model["model_id"], "support_url": model["support_url"],
                         "manual_url": c["url"], "public_file_id": c["public_file_id"],
                         "support_listed_date": c["listed_date"], "observed_cover_version": " / ".join(versions),
                         "pdf_pages": c["pdf_pages"], "pdf_bytes": c["bytes"],
                         "pdf_sha256": c["pdf_sha256"], "exact_SKU_in_cover": c["exact_SKU_in_native_cover"],
                         "purchased_SKU": "", "purchase_time_revision_verified": False,
                         "all_features_for_exact_SKU_verified": False, "runtime_registered": False,
                         "reference_cover": c["reference_cover_path"], "verdict": model["status"]})
    review_path = REF / "manual-cover-visual-review.json"
    result["visual_review"] = (json.loads(review_path.read_text(encoding="utf-8"))
                               if review_path.exists() else {"status": "PENDING_VISUAL_REVIEW", "new_OCR_runs": 0})
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (REF / "manual-reference-table.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# 15모델 공식 설명서 원본 수령·판본·SHA", "",
             "기록 ID: `DATA-REMAINING-INTAKE-20261008-01a1100e` · 확인일 2026-10-08 KST.", "",
             "정확 SKU 지원페이지에서 연결된 15모델/19모델별 PDF 후보를 조사했다. 공개 URL16개를 각각 한 번 받아 HTTP200·PDF 서명·native 표지를 확인했고, 전체 bytes SHA가 서로 다른 원본15개를 보존했다. MWJ25E의 두 URL은 같은 전체 SHA이며, MW20GDN/MW30EDN 및 DUE5BGL1E/DUE5BGE/DFE5BGE는 같은 URL을 공유한다.", "",
             "원 PDF는 새 local/private 폴더에만 보존한다. PR의 [전체 인계 JSON](manual-acquisition.json), [19행 CSV](manual-reference-table.csv), [발견 당시 후보](manual-link-candidates.json), 아래 표지 및 공식 원본 URL로 다시 받을 수 있다. 재수령한 bytes의 **전체 SHA**가 같아야 같은 원본으로 사용한다. 기존 생산 PDF/238후기/분할/계약/README는 변경하지 않았고 운영에는 등록하지 않았다.", "",
             "| 모델 | 관측 판본 / 쪽수 | 원 PDF / 표지 | 표지 정확SKU | 적용 상태 |",
             "|---|---|---|---|---|"]
    for model in result["models"]:
        for c in model["candidates"]:
            version = " / ".join(c["observed_cover_versions_normalized"])
            lines.append("| [" + model["model_id"] + "](" + model["support_url"] + ") | `" + version
                         + "` / " + str(c["pdf_pages"]) + " | [공식 PDF](" + c["url"] + ") · [표지]("
                         + c["reference_cover_path"] + ") | " + ("명시" if c["exact_SKU_in_native_cover"] else "공용/패턴")
                         + " | reference만 확보·전체기능/구매시점판 미확인 |")
    lines += ["", "## 모델·판본을 섞지 않는 기준", "",
              "- 표지에 정확 SKU를 직접 확인한 모델은 MW20GDN·MW30EDN·MW25B·MWJ25E·MWE25HD의 5개다. 이는 모델별 기능·코스·설치구성 전부를 승인한 결과가 아니다.",
              "- 나머지10모델은 정확 SKU 지원페이지 링크는 확인했지만 표지에 SKU가 직접 명시되지 않거나 공용 모델 패턴이다. 지원페이지 연결만으로 모든 기능·수치가 동일하다고 판단하지 않는다.",
              "- MW25B의 MFL68822520 Rev.22_090525와 MFL68822540 Rev.00_040826, MWE25HD의 같은 MFL68822533 Rev.01_121125/Rev.02_030326, D502MEE33의 두 문서는 각각 별도 SHA로 유지한다. 등록일이 늦다는 이유로 기존 원문을 교체하지 않는다.",
              "- 공용 DUE5/DFE5 PDF에서는 빌트인/프리스탠딩 및 개별 기능 적용을 추가로 대조해야 한다. 정확 구매SKU와 구매시점판은 전15모델 미확인이다.",
              "- PDP 팝업의 F19WDLP/SC5MBR62B 또는 중앙 선택 UI의 OLED/Windows11 예시는 선택된 주방 SKU의 설명서로 인정하지 않았다. 이번 확보는 모델별 지원페이지의 실제 공개 PDF 링크를 사용했다.",
              "- 지원목록의 등록일·PDF Rev 표기·FAQ 표시일·고객 후기 게시일은 서로 다른 필드다. PDF 표지를 읽는 native extraction16회 외에 OCR/모델 실행은0이다.", "",
              "## 다음 인수", "",
              "PM과 D2 담당자는 공개 URL·전체 SHA·판본·공용 적용 제한을 확인한 다음 필요한 모델/구간의 등록 여부를 결정한다. 이 참고팩은 생산팩 또는 승인된 Evidence를 대신하지 않는다. 원 리뷰 ID/게시일 필드/실사용·중복 계보는 [Q&A·후기 후보](qa-review-candidates.md)에서 별도로 인계한다.", ""]
    (REF / "manual-reference.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    values = sorted(by_sha.values(), key=lambda c: c["cover_versions"][0])
    for i in range(0, len(values), 3):
        sheet = Image.new("RGB", (3 * 720, 1080), "#eeeeee")
        draw = ImageDraw.Draw(sheet)
        for j, c in enumerate(values[i:i + 3]):
            image = Image.open(REF / c["reference_cover_path"])
            image.thumbnail((710, 1005))
            sheet.paste(image, (j * 720 + 5, 60))
            draw.text((j * 720 + 8, 8), re.sub(r"\s+", " ", c["cover_versions"][0]), font=font, fill="black")
            draw.text((j * 720 + 8, 32), c["pdf_sha256"][:16], font=font, fill="black")
            image.close()
        sheet.save(PRIVATE / ("cover-review-" + str(i // 3 + 1) + ".png"))
    print(json.dumps({"model_rows": len(result["models"]), "candidate_rows": len(rows),
                      "raw_URL_captures": len(by_url), "unique_SHA": len(by_sha),
                      "public_cover_files": len(by_sha), "new_HTTP": 0, "new_OCR": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
