from engine.evaluator import LucBatEvaluator
from scripts.build_sft_quality_subset import quality_decision


GOOD = "Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo là ghét nhau\nTrải qua một cuộc bể dâu\nNhững điều trông thấy mà đau đớn lòng"


def test_quality_gate_accepts_frozen_valid_luc_bat():
    evaluation, reasons = quality_decision({"text": GOOD}, LucBatEvaluator())
    assert evaluation["is_valid_lucbat"] is True
    assert reasons == []


def test_quality_gate_rejects_repetition():
    evaluation, reasons = quality_decision({"text": GOOD + "\nNhững điều trông thấy mà đau đớn lòng"}, LucBatEvaluator())
    assert "structure" in reasons
    assert "repeated_line" in reasons
