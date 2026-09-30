from pathlib import Path

from openfast_dataset.config import load_yaml


def test_load_yaml(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("answer: 42\n", encoding="utf-8")
    assert load_yaml(config)["answer"] == 42
