import pytest

from scripts.build_domain_adaptation_dataset import validate_split_integrity


def test_rejects_duplicate_cluster_across_splits():
    rows = [
        {"work_id": "a", "duplicate_cluster": "c", "split": "train"},
        {"work_id": "b", "duplicate_cluster": "c", "split": "dev"},
    ]
    with pytest.raises(ValueError, match="leaked"):
        validate_split_integrity(rows)


def test_accepts_cluster_safe_records():
    validate_split_integrity([
        {"work_id": "a", "duplicate_cluster": "c1", "split": "train"},
        {"work_id": "b", "duplicate_cluster": "c2", "split": "dev"},
    ])
