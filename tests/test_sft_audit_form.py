import json
from scripts.export_sft_audit_form import export_form


def test_export_form(tmp_path):
    source = tmp_path / "sample.jsonl"
    source.write_text(json.dumps({"work_id":"fsoft:1","split":"train","title":"t","url":"u","text":"tho"}, ensure_ascii=False) + "\n", encoding="utf-8")
    target = tmp_path / "form.csv"
    assert export_form(source, target) == 1
    contents = target.read_text(encoding="utf-8")
    assert "DA001" in contents and "naturalness_1_5" in contents
