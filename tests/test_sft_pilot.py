from scripts.build_sft_pilot import messages_for, select


def record(work_id, split, lines):
    return {
        "work_id": work_id, "split": split, "text": "\n".join(["mot hai ba bon nam sau"] * lines),
        "title": "chu de", "url": "u", "source_id": "s", "duplicate_cluster": work_id, "quality_gate": {},
    }


def test_select_balances_line_counts_and_keeps_splits():
    rows = [record(f"t{line}{index}", "train", line) for line in (4, 6, 8) for index in range(2)]
    chosen = select(rows, "train", 6)
    assert [len(row["text"].splitlines()) for row in chosen].count(4) == 2
    assert [len(row["text"].splitlines()) for row in chosen].count(6) == 2
    assert [len(row["text"].splitlines()) for row in chosen].count(8) == 2


def test_messages_have_no_cot_and_keep_poem_as_assistant():
    meta, messages = messages_for(record("x", "train", 4))
    assert meta["số câu"] == 4
    assert messages[-1]["role"] == "assistant"
    assert "<think>" not in messages[-1]["content"]
