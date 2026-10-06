"""Standard-library assembler for a new manual PDF/OCR review; no model execution."""
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKS = []


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def check(name, passed):
    CHECKS.append({"check": name, "passed": bool(passed)})
    if not passed:
        raise ValueError(name)


def normal(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def save_json(name, data):
    with (ROOT / name).open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def save_csv(name, rows, columns):
    with (ROOT / name).open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False)
                             if isinstance(row.get(k), (list, dict)) else row.get(k) for k in columns})


def code(value):
    return chr(96) + str(value) + chr(96)


def link(label, path):
    return "[" + label + "](<" + Path(path).as_posix() + ">)"


def cell(value):
    return str(value).replace("|", r"\|").replace("\n", "<br>")


baseline = load("input-baseline.json")
snapshots = load("input-snapshots.json")
manual = load("manual-observations.json")
ledger = load("inputs/ocr-error-ledger.json")
plan = load("inputs/ocr-table-review-plan.json")
raw = load("inputs/results.json")
crops = load("inputs/crop-manifest.json")
corpus = load("inputs/corpus-manifest.json")
renders = load("render-manifest.json")
details = load("detail-render-manifest.json")
check("14_regions", len(ledger["rows"]) == len(raw["results"]) == len(manual["regions"]) == 14)
check("all_plan_items", sorted(c["plan_index"] for c in manual["context_checks"] if "plan_index" in c) == [0,1,2])
check("zero_new_model_ocr", manual["additional_ocr_calls"] == manual["additional_product_model_calls"] == 0)
preservation = []
for before, snapshot in zip(baseline, snapshots, strict=True):
    after, copy_hash = digest(before["path"]), digest(snapshot["snapshot_path"])
    check("preserved:" + Path(before["path"]).name, after == copy_hash == before["sha256"])
    preservation.append({**before, "sha256_after": after, "snapshot_path": snapshot["snapshot_path"],
                         "snapshot_sha256": copy_hash, "unchanged": True})
raw_map = {r["region_id"]:(i,r) for i,r in enumerate(raw["results"])}
ledger_map = {r["region_id"]:(i,r) for i,r in enumerate(ledger["rows"])}
crop_map = {r["id"]:(c,r) for c in crops["cases"] for r in c["regions"]}
pdf_map = {Path(s["snapshot_path"]).name.split("-")[0]:s for s in snapshots if s["snapshot_path"].endswith(".pdf")}
render_map = {(r["model_id"],r["physical_pdf_page"]):r for r in renders}
detail_map = {(r["model_id"],r["physical_pdf_page"]):r for r in details}
for r in renders + details:
    check("raster_hash:" + Path(r["raster_path"]).name, digest(r["raster_path"]) == r["raster_sha256"])
regions = []
for obs in manual["regions"]:
    rid = obs["region_id"]
    li, saved = ledger_map[rid]
    ri, old = raw_map[rid]
    case, crop = crop_map[rid]
    model, page = saved["model_id"], saved["page"]
    pdf = pdf_map[model]
    check("PDF:" + rid, pdf["sha256"] == saved["source_pdf_sha256"] == case["source_pdf_sha256"])
    for key in ("gold_text","recognized","page","document_version","crop_sha256"):
        check("raw_ledger:" + rid + ":" + key, saved[key] == old[key])
    check("manual_source:" + rid, obs["source_text"] == saved["gold_text"])
    check("crop_hash:" + rid, crop["crop_sha256"] == saved["crop_sha256"])
    check("5_saved_attempts:" + rid, len(old["attempts"]) == 5 and all(
        a["status"] == "success" and a["recognized"] == saved["recognized"] for a in old["attempts"]))
    native_path = ROOT / "source-text" / (model + "-p" + str(page) + "-native.txt")
    native, phrase = normal(native_path.read_text(encoding="utf-8")), normal(obs["source_text"])
    check("native_phrase:" + rid, phrase in native)
    target = saved["field_target"]
    if target is not None:
        values = target["value"] if isinstance(target["value"],list) else [target["value"]]
        check("typed_main_value:" + rid, values == obs["source_values"])
    same = obs["source_text"] == saved["recognized"]
    difference = None if same else ("whitespace_omission" if obs["source_text"].replace(" ","") == saved["recognized"].replace(" ","")
                                   else "footnote_symbol_codepoint_change")
    image = render_map[(model,page)]
    detail = detail_map.get((model,page),image)
    ids = [e["id"] for e in corpus["evidence"] if e["source_pdf_sha256"] == pdf["sha256"]
           and e["original"]["page"] == page and phrase in normal(e["text"])]
    regions.append({
        **saved, "review_id":"REV-" + rid, "physical_pdf_page":page, "printed_page":page,
        "source_kind":"public", "source_pdf_original_path":pdf["source_path"],
        "source_pdf_snapshot_path":pdf["snapshot_path"],
        "source_text_transcribed_during_review":obs["source_text"], "source_review_status":"confirmed",
        "source_row_label":obs["row_label"], "manual_source_column_or_region":obs["column"],
        "source_primary_values":obs["source_values"], "explicit_units_in_ocr_crop":obs["source_units"],
        "ocr_text_status":"confirmed_match" if same else "confirmed_error", "confirmed_difference_kind":difference,
        "primary_number_error_found":False, "explicit_unit_error_found":False,
        "automatic_table_assignment_status":"unverified" if saved["table_row_crop"] else "not_in_scope",
        "automatic_table_assignment":None, "automatic_table_error":None,
        "crop_bbox_px_original":crop["crop_bbox_px"], "crop_dpi_original":case["dpi"],
        "source_phrase_occurrences_in_native_text":native.count(phrase),
        "current_ids_containing_exact_fragment_only":ids,
        "same_page_and_fragment_containment_do_not_prove_automatic_column_assignment":True,
        "ledger_json_pointer":"/rows/" + str(li), "saved_results_json_pointer":"/results/" + str(ri),
        "saved_attempts_verified_without_reexecution":5,
        "native_pdf_text_path":str(native_path), "native_pdf_text_sha256":digest(native_path),
        "source_raster_path":image["raster_path"], "source_raster_sha256":image["raster_sha256"],
        "detail_raster_path":detail["raster_path"], "detail_raster_sha256":detail["raster_sha256"],
        "notes":obs["notes"], "new_ocr_calls":0
    })
check("unique_region_ids", len({r["region_id"] for r in regions}) == 14)
dimension = ledger_map["OCR-MW-TABLE-01"][1]
check("mm_outside_crop_denominator", dimension["unit_total"] == 0 and dimension["explicit_unit_correct"] is None)
context = []
for spec in manual["context_checks"]:
    model, page = spec["model_id"], spec["page"]
    pdf = pdf_map[model]
    row = {**spec, "physical_pdf_page":page,"printed_page":page,"source_kind":"public",
           "source_pdf_sha256":pdf["sha256"],"source_pdf_snapshot_path":pdf["snapshot_path"],
           "source_pdf_original_path":pdf["source_path"],
           "source_raster_path":render_map[(model,page)]["raster_path"],
           "detail_raster_path":detail_map[(model,page)]["raster_path"],
           "automatic_table_assignment":None,"table_error":None,"new_ocr_calls":0}
    if "plan_index" in spec:
        expected = plan["source_table_checks"][spec["plan_index"]]
        check("plan_source:" + spec["review_id"], expected["model_id"] == model and expected["page"] == page)
        check("plan_null:" + spec["review_id"], expected["observed_table_assignment"] is None and expected["table_error"] is None)
        row["plan_item_preserved"] = expected
        row["plan_json_pointer"] = "/source_table_checks/" + str(spec["plan_index"])
    context.append(row)
power = ledger_map["OCR-MW-TABLE-05"][1]
pattern = r"\d+(?:\.\d+)?"
gold_numbers = [float(n) for n in re.findall(pattern,power["gold_text"])]
ocr_numbers = [float(n) for n in re.findall(pattern,power["recognized"])]
check("footnote_number_already_in_source", gold_numbers == ocr_numbers == [1000.0,1.0])
check("saved_field_failure", power["observed_values"] == ocr_numbers and power["strict_numeric_field_correct"] is False)
diagnosis = {"review_id":"CTX-MW-05","region_id":"OCR-MW-TABLE-05","source_main_value":1000,"unit":"W",
             "source_footnote_id":"*1","recognized_footnote_id":"∗1","source_star_codepoint":"U+002A",
             "recognized_star_codepoint":"U+2217","generic_digit_tokens_of_gold":gold_numbers,
             "generic_digit_tokens_of_saved_ocr":ocr_numbers,"saved_strict_numeric_field_correct":False,
             "diagnosis":"footnote number counted as another value; OCR did not invent an extra digit",
             "correction_applied":False}
versions = {}
for model,pdf in pdf_map.items():
    version = next(r["document_version"] for r in regions if r["model_id"] == model)
    cover = normal((ROOT/"source-text"/(model+"-p1-native.txt")).read_text(encoding="utf-8"))
    check("cover_visual_revision:" + model, manual["cover_visual_versions"][model] == version)
    versions[model] = {"document_version":version,"source_kind":"public","pdf_sha256":pdf["sha256"],
                      "snapshot_pdf_path":pdf["snapshot_path"],"original_pdf_path":pdf["source_path"],
                      "reviewed_physical_pdf_pages":sorted({r["page"] for r in regions if r["model_id"] == model}),
                      "cover_visually_reviewed":True,
                      "cover_native_text_contains_revision": version in cover,
                      "cover_native_text_limitation": "pypdf extracted cover characters are corrupted; use visually verified cover and PDF hash",
                      "cover_raster_path": render_map[(model,1)]["raster_path"],
                      "cover_raster_sha256": render_map[(model,1)]["raster_sha256"]}
statuses = Counter(r["ocr_text_status"] for r in regions)
kinds = Counter(r["confirmed_difference_kind"] for r in regions)
check("6_differences_8_matches", statuses["confirmed_error"] == 6 and statuses["confirmed_match"] == 8)
check("5_spaces_1_star", kinds["whitespace_omission"] == 5 and kinds["footnote_symbol_codepoint_change"] == 1)
check("70_saved_attempts", sum(len(r["attempts"]) for r in raw["results"]) == 70)
summary = {"saved_ocr_regions_reviewed":14,"saved_measured_attempts_cross_checked":70,
           "confirmed_text_difference_regions":6,"confirmed_exact_match_regions":8,
           "whitespace_omission_regions":5,"footnote_symbol_codepoint_change_regions":1,
           "primary_number_errors_in_scored_crops":0,"explicit_unit_errors_in_scored_crops":0,
           "separate_saved_numeric_field_evaluation_issue":1,"planned_source_checks_confirmed":3,
           "planned_automatic_table_checks_unverified":3,"additional_context_rows":len(context)-3,
           "context_source_confirmed":sum(r["source_status"] == "confirmed" for r in context),
           "context_source_unverified":sum(r["source_status"] == "unverified" for r in context),
           "automatic_table_model_column_accuracy":None,"automatic_table_error_rate":None,
           "additional_product_model_calls":0,"additional_ocr_calls":0,"original_inputs_unchanged":len(preservation),
           "full_page_renders":len(renders),"detail_renders":len(details)}
stamp = datetime.now(timezone(timedelta(hours=9))).isoformat()
execution_notes = manual["execution_notes"] + [
    "첫 집계 스크립트 파일 생성 시 도구 JavaScript 문자열 구문 오류로 실행 전 실패. 그 시도는 파일/자료를 변경하거나 모델/OCR을 실행하지 않았으며 새 집계 스크립트 작성으로 복구."
]
review = {"review_id":ROOT.name,"reviewed_at_kst":stamp,"reviewer":manual["reviewer"],"independent_review":False,
          "user_instruction":"기존 ocr-error-ledger·ocr-table-review-plan·원본 PDF 대조; 새 고유 폴더의 검수표; 기존 결과·코드·공용 README 수정 금지; 새 모델/OCR 호출 금지; 확인 오류/미확인 구분",
          "reviewed_saved_data_main_commit":corpus["main_commit"],"dataset_version":corpus["dataset_version"],
          "dataset_file_sha256_recorded_in_original_manifest":corpus["dataset_file_sha256"],
          "source_versions":versions,"summary":summary,"regions":regions,"table_and_context_checks":context,
          "footnote_numeric_field_diagnosis":diagnosis,"original_ocr_summary_preserved":ledger["original_summary"],
          "execution_notes":execution_notes,"source_preservation":preservation,"checks":CHECKS,
          "new_repository_code_execution":False,"existing_repository_files_edited":False,
          "shared_README_edited":False,"remote_publication_performed":False,
          "remaining":["Three automatic table assignments are unverified; existing full-table output is needed.",
                       "FR type-to-SKU mapping and the earlier external 5cm/manual 10cm applicability conflict remain unverified.",
                       "#14 overall retrieval/model comparison, #13 live handoff and PM acceptance are not completed by this manual review."]}
save_json("review.json",review)
save_json("preservation-check.json",{"checked_at_kst":stamp,"unchanged":True,"input_count":len(preservation),
                                  "files":preservation,"writes_limited_to_new_review_folder":str(ROOT)})
save_json("verification.json",{"summary":summary,"all_passed":True,"checks":CHECKS})
save_csv("region-review.csv",regions,[
    "review_id","region_id","model_id","document_version","source_pdf_sha256","physical_pdf_page","printed_page",
    "source_row_label","manual_source_column_or_region","source_text_transcribed_during_review","recognized",
    "ocr_text_status","confirmed_difference_kind","source_primary_values","explicit_units_in_ocr_crop",
    "numeric_correct","numeric_total","strict_numeric_field_correct","observed_values","explicit_unit_correct","unit_total",
    "automatic_table_assignment_status","automatic_table_assignment","automatic_table_error","source_pdf_snapshot_path",
    "source_raster_path","detail_raster_path","crop_sha256","crop_bbox_px_original",
    "current_ids_containing_exact_fragment_only","notes"])
save_csv("table-context-review.csv",context,[
    "review_id","model_id","physical_pdf_page","printed_page","subject","source_status","evaluation_status",
    "source_reference","related_regions","evidence_ids","automatic_table_assignment","table_error",
    "source_pdf_sha256","source_pdf_snapshot_path","source_raster_path","detail_raster_path","notes","next_action"])
lines = [
    "# #14 OCR 표·숫자·단위·각주 검수표","",
    "검수 ID: "+code(ROOT.name)+" · 작성: "+code(stamp),"",
    "기존 OCR 14영역·70회 결과와 세 원본 PDF를 대조했다. **확인된 문자 차이 6영역(공백 누락 5, 별표 변경 1), 일치 8영역**이다. 기존 측정 crop의 본값 숫자·명시적 단위 오류는 발견하지 않았다. **각주 번호를 숫자 필드에 포함한 기존 평가 실패 1건**은 별도 기록했다. 원 계획 3항목의 기대 원문은 확인했지만 자동 표의 열·모델·물리량 연결은 출력 부재로 **모두 미확인/null**이다.","",
    "새 제품 모델/OCR 호출 0회. 기존 결과·코드·공용 README 수정 0개. 기존 입력 13개와 새 사본의 SHA256을 대조했다. 현재 대화의 수동 시각 검수이며 별도 독립 검수자 평가로 표시하지 않는다. 이 검수로 #14 전체 완료를 선언하지 않는다.","",
    "## 자료 버전과 범위","",
    "기존 자료의 main 기준: "+code(corpus["main_commit"])+" · 자료 버전: "+code(corpus["dataset_version"])+". 최신 main의 새 실행 성적을 뜻하지 않는다. prepared/bundle의 ledger와 plan이 각각 byte 동일한 것을 확인했다.","",
    "| 제품 | 설명서 개정 | 확인 본문 쪽 | 원본 사본·SHA256 |","|---|---|---|---|"]
for model,v in versions.items():
    lines.append("| "+code(model)+" | "+code(v["document_version"])+" | "+
                 ", ".join(map(str,v["reviewed_physical_pdf_pages"]))+" (표지 p1도 확인) | "+
                 link("PDF",v["snapshot_pdf_path"])+" · "+code(v["pdf_sha256"])+" |")
lines += ["",
    "본문 6쪽의 물리 PDF 쪽과 인쇄 쪽이 일치한다. 전체 설명서 모든 페이지의 OCR 검수가 아니다. 원본 9쪽 렌더링과 표 상세 3장을 시각 확인했으며 PDF 문자층은 보조 대조에만 사용했다.","",
    "원 기록: "+link("오류 ledger",ROOT/"inputs/ocr-error-ledger.json")+" · "+
    link("검수 계획",ROOT/"inputs/ocr-table-review-plan.json")+" · "+link("과거 OCR 원결과",ROOT/"inputs/results.json")+
    " · "+link("원 입력 보존 확인",ROOT/"preservation-check.json"),"",
    "## 14영역 원문·저장 OCR 대조","",
    "‘확인 오류’는 문자의 차이를 뜻한다. 숫자 본값·단위 오류나 전체 표 추출 실패로 확대하지 않는다. 기존 숫자/단위 분모 15/12와 엄격한 숫자 필드 11을 보존하며 crop 밖의 단위·행 이름·조건의 자동 연결은 미확인이다.","",
    "| 영역 / 쪽 | 원문 | 저장 OCR | 문자 판정 | 원문 행·열·조건 |","|---|---|---|---|---|"]
for r in regions:
    status = "일치" if r["ocr_text_status"] == "confirmed_match" else (
        "확인 오류: 공백" if r["confirmed_difference_kind"] == "whitespace_omission" else "확인 오류: 별표 코드점")
    lines.append("| "+code(r["region_id"])+" · "+link("p"+str(r["page"]),r["detail_raster_path"])+" | "+
                 code(cell(r["source_text_transcribed_during_review"]))+" | "+code(cell(r["recognized"]))+" | "+
                 status+" | "+cell(r["source_row_label"])+"; "+cell(r["manual_source_column_or_region"])+". "+cell(r["notes"])+" |")
lines += ["",
    "공백 누락은 5영역에서 문자 8개(전자레인지 외형 치수의 × 양옆 공백 4개 포함)다. X와 ×는 설명서별 표기를 그대로 대조했다. 기존 명시적 단위 12/12에는 MW 외형 치수의 mm가 포함되지 않는다.","",
    "## 원 계획 3항목","",
    "| 계획 | 원본 확인 기준 | 자동 추출 판정 | 근거 ID·이후 확인 |","|---|---|---|---|"]
for c in context:
    if "plan_index" in c:
        lines.append("| "+code(c["review_id"])+" · "+cell(c["subject"])+" | "+cell(c["source_reference"])+
                     " | **미확인**; observed_table_assignment=null, table_error=null | "+
                     ", ".join(code(i) for i in c["evidence_ids"])+". "+cell(c["next_action"])+" |")
lines += ["","## 표 문맥·단위·각주 상세","",
    "원문 확인과 추출 성능을 별도 열로 기록했다. 원문에서 기대 연결을 확인한 사실은 자동 추출 성공이 아니다. ‘미확인’은 추출 출력 부재 또는 출처/모델 적용의 미확인이며 오류로 확정하지 않는다.","",
    "| 항목 | 원문·자료 확인 | 저장 출력/평가 판정 | 근거와 남은 확인 |","|---|---|---|---|"]
for c in context:
    if "plan_index" not in c:
        source_status = "원문 확인" if c["source_status"] == "confirmed" else "적용/출처 미확인"
        status = "확인 오류: 기존 숫자 필드 평가" if c["evaluation_status"] == "confirmed_error" else "미확인"
        lines.append("| "+code(c["review_id"])+" · "+cell(c["subject"])+" | "+source_status+": "+
                     cell(c["source_reference"])+" | "+status+" | "+cell(c["notes"])+" "+cell(c["next_action"])+" |")
lines += ["","### 각주 번호 혼입의 원인","",
    "OCR-MW-TABLE-05 원문은 "+code("1000 W*1")+", 저장 OCR은 "+code("1000 W∗1")+
    "이다. 본값은 1000 W이고 1은 원문에 있는 각주 번호다. 원문과 저장 문자열 모두 일반 숫자 검색으로 [1000, 1]이 되므로 OCR이 새 숫자 1을 만든 것으로 판단하지 않는다. 기존 ledger의 observed_values=[1000.0,1.0], strict_numeric_field_correct=false는 그대로 보존했다. **기존 평가/필드 처리에서 본값과 각주를 분리할 필요가 있는 확인된 문제**다. 코드·gold·원 성적 10/11은 변경하지 않았다.","",
    "DATA003-MW23FDI-M06 현재 인용에는 Max.와 각주 본문이 보존되어 있다. M07은 정격 소비전력 1570 W를 인용한다. DUE D03 인용은 두 열의 치수·조건을 담지만 무게 행 이전에 끝난다. 같은 페이지 ID만으로 45 kg 등 모든 값의 인용 동등성을 주장하지 않는다. JSON은 같은 페이지 ID와 실제 구절 포함 ID를 분리하며, 구절 포함도 자동 열 연결의 성공으로 사용하지 않는다.","",
    "## 실행·검사와 남은 일",""]
lines += ["- "+note for note in execution_notes]
lines += ["",
    "집계 일관성 "+str(len(CHECKS))+"항목 전부 일치. 저장 파일·해시·문자·시도 수·원문 구절·검수표 연결 확인이며 저장소 회귀 검사나 새 모델/OCR 성능 측정이 아니다.","",
    "자동 표의 실제 저장 출력과 모델/헤더/물리량/각주 연결 검사가 남았다. 같은 70회 OCR의 반복 실행을 제안하지 않았다. 기존 전체 표 출력이 있다면 이 표의 미확인 항목을 후속 검수할 수 있다. 냉장고 유형-SKU 연결과 C01 출처 상충은 미해결이다. #13 실제 handoff·새 corpus 검색 비교·PM 인수 등 #14의 다른 요구도 완료로 표시하지 않는다.","",
    "검수 원본: "+link("review.json",ROOT/"review.json")+" · "+link("14영역 CSV",ROOT/"region-review.csv")+" · "+
    link("표/문맥 19항목 CSV",ROOT/"table-context-review.csv")+" · "+link("검사 기록",ROOT/"verification.json")+
    " · "+link("수동 관찰",ROOT/"manual-observations.json"),""]
with (ROOT/"검수표.md").open("x",encoding="utf-8") as f:
    f.write("\n".join(lines))
files = [{"relative_path":p.relative_to(ROOT).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p)}
         for p in sorted(ROOT.rglob("*")) if p.is_file() and p.name != "artifact-manifest.json"]
save_json("artifact-manifest.json",{
    "created_at_kst":stamp,"output_root":str(ROOT),"summary":summary,"files":files,
    "assembler_sha256":digest(__file__),
    "runtime":{"assembler":"Python standard library -I -S -B -X utf8","pdf_rendering":"Poppler 26.07.0","native_pdf_text":"pypdf 6.10.0"},
    "new_ocr_calls":0,"additional_product_model_calls":0,"git_commit_or_remote_publication":False})
print(json.dumps({"review_root":str(ROOT),"summary":summary,"consistency_checks":len(CHECKS),"all_passed":True,
                  "files_in_manifest":len(files)},ensure_ascii=False,indent=2))
