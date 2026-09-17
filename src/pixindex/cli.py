from __future__ import annotations

import typer

from pixindex import __version__

app = typer.Typer(
    no_args_is_help=True,
    help="Index pictures in a folder or S3 prefix. Query the catalog. Export it.",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Index pictures in a folder or S3 prefix."""


@app.command()
def index(
    source: str = typer.Argument(help="Local folder or s3://bucket/prefix."),
) -> None:
    """Walk a local folder or S3 prefix and catalog images."""
    _not_implemented("index")


@app.command()
def search(
    camera: str | None = typer.Option(
        None, help="Camera make or model contains this text."
    ),
    after: str | None = typer.Option(
        None, help="Captured on or after this date (YYYY-MM-DD)."
    ),
    before: str | None = typer.Option(
        None, help="Captured on or before this date (YYYY-MM-DD)."
    ),
    has_gps: bool | None = typer.Option(
        None,
        "--has-gps/--no-gps",
        help="Only images with or without GPS.",
    ),
    ext: str | None = typer.Option(None, help="File extension, for example jpg."),
    min_size: str | None = typer.Option(
        None, help="Minimum file size, for example 5mb."
    ),
    source: str | None = typer.Option(None, help="Limit to one indexed root."),
) -> None:
    """Filter the catalog and print matching URIs."""
    _not_implemented("search")


@app.command()
def stat() -> None:
    """Print a summary of the catalog."""
    _not_implemented("stat")


@app.command()
def export(
    output_format: str = typer.Argument(help="csv or json.", metavar="FORMAT"),
) -> None:
    """Write matching rows to csv or json."""
    _not_implemented("export")


def _not_implemented(command: str) -> None:
    typer.echo(f"{command} is not implemented yet.", err=True)
    raise typer.Exit(code=1)
