from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from pixindex.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("index", "search", "stat", "export"):
        assert command in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_index_s3_is_not_implemented() -> None:
    result = runner.invoke(app, ["index", "s3://bucket/photos"])
    assert result.exit_code == 1
    assert "S3 is not implemented yet" in result.stderr


def test_index_missing_path(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["--db", str(tmp_path / "index.sqlite"), "index", str(tmp_path / "missing")]
    )
    assert result.exit_code == 1
    assert "Not found" in result.stderr


def test_index_local_folder(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (16, 9), color="red").save(photos / "shot.png")

    db = tmp_path / "index.sqlite"
    result = runner.invoke(app, ["--db", str(db), "index", str(photos)])
    assert result.exit_code == 0
    assert "Indexed 1, skipped 0, failed 0." in result.stdout
    assert db.is_file()


def test_stat_missing_catalog(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--db", str(tmp_path / "missing.sqlite"), "stat"])
    assert result.exit_code == 1
    assert "No catalog" in result.stderr


def test_stat_after_index(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (16, 9), color="red").save(photos / "shot.png")
    db = tmp_path / "index.sqlite"

    runner.invoke(app, ["--db", str(db), "index", str(photos)])
    result = runner.invoke(app, ["--db", str(db), "stat"])

    assert result.exit_code == 0
    assert "1 picture" in result.stdout
    assert "With GPS: 0 of 1 (0%)" in result.stdout


def test_search_missing_catalog(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--db", str(tmp_path / "missing.sqlite"), "search"])
    assert result.exit_code == 1
    assert "No catalog" in result.stderr


def test_search_lists_paths(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (8, 8), color="red").save(photos / "shot.png")
    db = tmp_path / "index.sqlite"

    runner.invoke(app, ["--db", str(db), "index", str(photos)])
    result = runner.invoke(app, ["--db", str(db), "search", "--ext", "png"])

    assert result.exit_code == 0
    assert str((photos / "shot.png").resolve()) in result.stdout


def test_search_bad_date(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["--db", str(tmp_path / "index.sqlite"), "search", "--after", "nope"]
    )
    assert result.exit_code == 1
    assert "YYYY-MM-DD" in result.stderr
