from pathlib import Path

from PIL import Image, ImageDraw
from typer.testing import CliRunner

from pixindex.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("index", "embed", "search", "stat", "export", "duplicates", "check"):
        assert command in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.2.2"


def test_index_s3_uses_store(monkeypatch, tmp_path: Path) -> None:
    from pixindex.index import IndexResult

    def fake_index_source(source: str, db_path, store=None):
        assert source == "s3://bucket/photos"
        return IndexResult(indexed=3, skipped=1, failed=0)

    monkeypatch.setattr("pixindex.cli.index_source", fake_index_source)
    result = runner.invoke(
        app, ["--db", str(tmp_path / "index.sqlite"), "index", "s3://bucket/photos"]
    )
    assert result.exit_code == 0
    assert "Indexed 3, skipped 1, failed 0." in result.stdout


def test_index_s3_bad_uri() -> None:
    result = runner.invoke(app, ["index", "s3://"])
    assert result.exit_code == 1
    assert "bucket" in result.stderr


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


def test_export_csv(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (8, 8), color="red").save(photos / "shot.png")
    db = tmp_path / "index.sqlite"

    runner.invoke(app, ["--db", str(db), "index", str(photos)])
    result = runner.invoke(app, ["--db", str(db), "export", "csv"])

    assert result.exit_code == 0
    assert result.stdout.startswith("uri,source,size,")
    assert "shot.png" in result.stdout


def test_embed_and_word_search(tmp_path: Path, monkeypatch) -> None:
    from color_embedder import ColorEmbedder

    monkeypatch.setattr("pixindex.cli.load_embedder", ColorEmbedder)
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (16, 16), color="red").save(photos / "red.png")
    Image.new("RGB", (16, 16), color="blue").save(photos / "blue.png")
    db = tmp_path / "index.sqlite"

    embedded = runner.invoke(app, ["--db", str(db), "embed"])
    assert embedded.exit_code == 1
    assert "No catalog" in embedded.stderr

    runner.invoke(app, ["--db", str(db), "index", str(photos)])
    embedded = runner.invoke(app, ["--db", str(db), "embed"])
    assert embedded.exit_code == 0
    assert "Embedded 2, skipped 0, failed 0." in embedded.stdout
    assert "Model color." in embedded.stdout

    found = runner.invoke(app, ["--db", str(db), "search", "red", "--limit", "1"])
    assert found.exit_code == 0
    assert found.stdout.strip().endswith("red.png")
    assert "blue.png" not in found.stdout


def test_word_search_without_embed_explains_why(tmp_path: Path, monkeypatch) -> None:
    from pixindex.embedder import EmbedError

    def missing():
        raise EmbedError("Picture search needs an extra install: pip install 'pixindex[embed]'")

    monkeypatch.setattr("pixindex.cli.load_embedder", missing)
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (8, 8), color="red").save(photos / "shot.png")
    db = tmp_path / "index.sqlite"
    runner.invoke(app, ["--db", str(db), "index", str(photos)])

    result = runner.invoke(app, ["--db", str(db), "search", "red"])
    assert result.exit_code == 1
    assert "pixindex[embed]" in result.stderr


def test_duplicates_command_prints_the_group(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    image = Image.new("RGB", (32, 32), "white")
    ImageDraw.Draw(image).rectangle((0, 0, 15, 31), fill="black")
    image.save(photos / "a.png")
    image.save(photos / "b.png")
    db = tmp_path / "index.sqlite"
    runner.invoke(app, ["--db", str(db), "index", str(photos)])

    result = runner.invoke(app, ["--db", str(db), "duplicates"])
    assert result.exit_code == 0
    assert "a.png" in result.stdout
    assert "b.png" in result.stdout
    assert "1 group." in result.stderr


def test_duplicates_rejects_a_negative_distance(tmp_path: Path) -> None:
    db = tmp_path / "index.sqlite"
    db.write_bytes(b"")
    result = runner.invoke(app, ["--db", str(db), "duplicates", "--distance", "-1"])
    assert result.exit_code == 1
    assert "--distance" in result.stderr


def test_check_uses_the_stand_in_model(monkeypatch) -> None:
    from color_embedder import ColorEmbedder

    monkeypatch.setattr("pixindex.cli.load_embedder", ColorEmbedder)
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0
    assert "Picture search: 2/2" in result.stdout
    assert "Duplicates: 1/1" in result.stdout


def test_export_bad_format(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--db", str(tmp_path / "x.sqlite"), "export", "xlsx"])
    assert result.exit_code == 1
    assert "csv or json" in result.stderr
