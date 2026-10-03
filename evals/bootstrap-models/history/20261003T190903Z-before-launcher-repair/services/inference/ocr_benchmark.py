"""CPU Korean text-line recognition smoke; no PDF layout/detection or Agent claim."""

import importlib.metadata
import json
import os
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

MODEL_ID = "PaddlePaddle/korean_PP-OCRv5_mobile_rec"
REVISION = "c02ecaf1f22bfd1c618cce154fd19185b47e663a"


def distance(left, right):
    previous = list(range(len(right) + 1))
    for index, first in enumerate(left, 1):
        row = [index]
        for offset, second in enumerate(right, 1):
            row.append(min(row[-1] + 1, previous[offset] + 1, previous[offset - 1] + (first != second)))
        previous = row
    return previous[-1]


def main():
    # Set caches before importing PaddleOCR so no existing project/model caches are used.
    cache = Path("/dev/shm") / f"lg-ax-{os.environ['USER']}"
    os.environ["HF_HOME"] = str(cache / "huggingface")
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache / "paddlex")
    os.environ["PADDLE_HOME"] = str(cache / "paddle")
    os.environ["XDG_CACHE_HOME"] = str(cache / "xdg-cache")
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from huggingface_hub import HfApi, snapshot_download
    from paddleocr import TextRecognition
    from PIL import Image, ImageDraw, ImageFont

    info = HfApi().model_info(MODEL_ID, revision=REVISION)
    if info.sha != REVISION:
        raise ValueError("OCR model revision differs from the bootstrap lock")
    snapshot = Path(snapshot_download(MODEL_ID, revision=REVISION, allow_patterns=["config.json", "inference.*"]))
    font_path = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    font = ImageFont.truetype(str(font_path), 42)
    fixtures = ["선반을 분리하기 전에 식품을 모두 옮겨 주세요", "전자레인지에 금속 용기를 넣지 마세요"]
    target = Path("evals/bootstrap-models/ocr")
    target.mkdir(parents=True, exist_ok=True)
    images = []
    for index, text in enumerate(fixtures, 1):
        bounds = font.getbbox(text)
        image = Image.new("RGB", (bounds[2] - bounds[0] + 24, bounds[3] - bounds[1] + 20), "white")
        ImageDraw.Draw(image).text((12 - bounds[0], 10 - bounds[1]), text, font=font, fill="black")
        image_path = target / f"korean-text-{index}.png"
        image.save(image_path)
        images.append((text, image_path))
    started = time.perf_counter()
    model = TextRecognition(model_name="korean_PP-OCRv5_mobile_rec", model_dir=str(snapshot), device="cpu", enable_mkldnn=False, cpu_threads=4)
    load_seconds = time.perf_counter() - started
    results = []
    for text, image_path in images:
        started = time.perf_counter()
        prediction = next(iter(model.predict(input=str(image_path), batch_size=1)))
        milliseconds = (time.perf_counter() - started) * 1000
        recognized = prediction["rec_text"]
        results.append({"image": image_path.as_posix(), "image_sha256": sha256(image_path.read_bytes()).hexdigest(),
                        "expected": text, "recognized": recognized, "rec_score": float(prediction["rec_score"]),
                        "character_error_rate": distance(text, recognized) / len(text),
                        "character_error_rate_without_spaces": distance(text.replace(" ", ""), recognized.replace(" ", "")) / len(text.replace(" ", "")),
                        "latency_ms": round(milliseconds, 3), "exact_match": text == recognized})
    output = {"status": "executed", "experiment_kind": "bootstrap_korean_textline_ocr", "timestamp_utc": datetime.now(UTC).isoformat(),
              "benchmark_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "model": {"model_id": MODEL_ID, "revision": REVISION, "license": str(info.card_data.license), "source": f"https://huggingface.co/{MODEL_ID}",
                        "downloaded_size_bytes": sum(path.stat().st_size for path in snapshot.iterdir() if path.is_file()),
                        "downloaded_weight_files": {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(snapshot.iterdir()) if path.is_file()}},
              "device": "cpu", "model_load_seconds": round(load_seconds, 3), "font": "NotoSansCJK-Regular.ttc (system font, not redistributed)",
              "settings": {"font_px": 42, "cpu_threads": 4, "enable_mkldnn": False},
              "runtime_versions": {name: importlib.metadata.version(name) for name in ["paddlepaddle", "paddleocr", "paddlex", "pillow", "numpy"]},
              "results": results, "agent_implemented": False,
              "limits": ["2 clean synthetic Korean text-line images; not held-out OCR accuracy", "No text detection, page layout, tables, scans or document evidence integration tested", "Recognition confidence is model output, not verified semantic accuracy"]}
    Path("evals/bootstrap-models/ocr-results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"stage": "completed", "results": results}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
