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


def test_index_is_not_implemented() -> None:
    result = runner.invoke(app, ["index", "./photos"])
    assert result.exit_code == 1
    assert "not implemented yet" in result.stderr
