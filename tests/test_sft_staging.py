import csv
from scripts.build_sft_staging import cluster_rows, load_luc_bat_rows, normalize_text


def test_normalize_text():
    assert normalize_text("  Ca\r\n\r\n dao  ") == "Ca\ndao"


def test_exact_dedup_and_split(tmp_path):
    source = tmp_path / "source.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "content", "title", "url", "genre"])
        writer.writeheader()
        writer.writerows([
            {"id": "1", "content": "mot hai ba", "title": "a", "url": "u1", "genre": "luc bat"},
            {"id": "2", "content": "mot hai ba", "title": "b", "url": "u2", "genre": "luc bat"},
            {"id": "3", "content": "khac", "title": "c", "url": "u3", "genre": "7 chu"},
        ])
    rows, genres = load_luc_bat_rows(source)
    staged, stats = cluster_rows(rows)
    assert genres["luc bat"] == 2
    assert len(staged) == 1
    assert stats["exact_duplicates_removed"] == 1
    assert staged[0]["split"] in {"train", "dev", "test"}
