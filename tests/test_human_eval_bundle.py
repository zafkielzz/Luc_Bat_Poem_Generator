import csv
import json

from scripts.export_human_eval_bundle import export_bundle


def _dump(path, rows):
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _row(prompt_id, lines, poem):
    return {
        "prompt_id": prompt_id,
        "prompt": f"prompt {prompt_id}",
        "metadata": {"số câu": lines},
        "candidates": [{"poem": poem}],
    }


def test_export_is_blind_paired_and_stratified(tmp_path):
    baseline = []
    sft = []
    for lines in (4, 6, 8):
        for index in range(3):
            prompt_id = f"T{lines}-{index}"
            baseline.append(_row(prompt_id, lines, f"baseline {prompt_id}"))
            sft.append(_row(prompt_id, lines, f"sft {prompt_id}"))
    baseline_path = tmp_path / "baseline.json"
    sft_path = tmp_path / "sft.json"
    _dump(baseline_path, baseline)
    _dump(sft_path, sft)

    form_path, key_path = export_bundle(baseline_path, sft_path, tmp_path / "bundle", 6, 42)
    with form_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    key = json.loads(key_path.read_text(encoding="utf-8"))

    assert len(rows) == 12
    assert all("variant" not in row for row in rows)
    assert all(not row["naturalness"] for row in rows)
    assert {item["variant"] for item in key["items"]} == {"baseline", "sft"}
    assert {row["num_lines"] for row in rows} == {"4", "6", "8"}
