from acts.config import ACTS_MANIFEST, DATA_DIR, GOLDEN_SET, PROJECT_ROOT


def test_paths_point_into_repository():
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert DATA_DIR == PROJECT_ROOT / "data" / "raw"
    assert ACTS_MANIFEST.parent == DATA_DIR


def test_golden_set_is_in_eval_dir():
    assert GOLDEN_SET == PROJECT_ROOT / "eval" / "golden.jsonl"
