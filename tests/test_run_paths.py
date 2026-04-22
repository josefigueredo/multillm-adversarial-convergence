"""Tests for run path construction."""

from pathlib import Path

from src.run_paths import RunPaths


def test_run_paths_builds_expected_artifact_locations(tmp_path: Path):
    paths = RunPaths.for_output_dir(tmp_path / "run-a")

    assert paths.output_dir == tmp_path / "run-a"
    assert paths.iterations_dir == tmp_path / "run-a" / "iterations"
    assert paths.manifest == tmp_path / "run-a" / "run_manifest.json"
    assert paths.prompt_snapshot == tmp_path / "run-a" / "prompt_snapshot.json"
    assert paths.rerun_script == tmp_path / "run-a" / "rerun.sh"
    assert paths.portfolio == tmp_path / "portfolio.json"
