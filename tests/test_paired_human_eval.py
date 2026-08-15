import csv
import json

from scripts.export_paired_human_eval import export_paired_bundle


def _row(prompt_id, lines, poem):
    return {
        "prompt_id": prompt_id,
        "prompt": f"prompt {prompt_id}",
        "metadata": {"số câu": lines},
        "candidates": [{"poem": poem}],
    }


def test_paired_export_keeps_variants_blind(tmp_path):
    base, sft = [], []
    for lines in (4, 6, 8):
        for index in range(3):
            prompt_id = f"T{lines}-{index}"
            base.append(_row(prompt_id, lines, f"base {prompt_id}"))
            sft.append(_row(prompt_id, lines, f"sft {prompt_id}"))
    base_path, sft_path = tmp_path / "base.json", tmp_path / "sft.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    sft_path.write_text(json.dumps(sft), encoding="utf-8")

    form_path, key_path = export_paired_bundle(base_path, sft_path, tmp_path / "bundle", 6, 42)
    with form_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    key = json.loads(key_path.read_text(encoding="utf-8"))

    assert len(rows) == 6
    assert all("baseline" not in row and "sft" not in row for row in rows)
    assert all(row["preference"] == "" for row in rows)
    assert all({item["A"], item["B"]} == {"baseline", "sft"} for item in key["items"])


def test_paired_export_accepts_explicit_prompt_ids(tmp_path):
    base = [_row(f"T{index}", 4, f"base {index}") for index in range(3)]
    sft = [_row(f"T{index}", 4, f"sft {index}") for index in range(3)]
    base_path, sft_path = tmp_path / "base.json", tmp_path / "sft.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    sft_path.write_text(json.dumps(sft), encoding="utf-8")
    form_path, key_path = export_paired_bundle(
        base_path, sft_path, tmp_path / "bundle", 2, 42,
        prompt_ids=["T2", "T0"], version="tet4-human-eval-paired-v1",
    )
    key = json.loads(key_path.read_text(encoding="utf-8"))
    assert key["version"] == "tet4-human-eval-paired-v1"
    assert {item["prompt_id"] for item in key["items"]} == {"T0", "T2"}
