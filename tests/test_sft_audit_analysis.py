import csv
from scripts.analyze_sft_audit import analyze


def test_analyze_passes_at_eighty_percent(tmp_path):
    path = tmp_path / "ratings.csv"
    fields = ["naturalness_1_5", "imagery_coherence_1_5", "sensitive_or_unusable_0_1", "decision_accept_reject"]
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for index in range(10):
            writer.writerow({"naturalness_1_5":"4","imagery_coherence_1_5":"4","sensitive_or_unusable_0_1":"0","decision_accept_reject":"accept" if index < 8 else "reject"})
    assert analyze(path)["pilot_gate_passed"] is True
