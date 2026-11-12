from acts.config import ACTS_MANIFEST, DATA_DIR, PROJECT_ROOT


def test_paths_point_into_repository():
    assert (PROJECT_ROOT / "pyproject.toml").exists()
    assert DATA_DIR == PROJECT_ROOT / "data" / "raw"
    assert ACTS_MANIFEST.parent == DATA_DIR
