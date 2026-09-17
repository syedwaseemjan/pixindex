from __future__ import annotations

from pathlib import Path

import typer

from pixindex import __version__
from pixindex.db import resolve_db_path
from pixindex.index import index_local

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
    ctx: typer.Context,
    db: Path | None = typer.Option(
        None,
        "--db",
        help="SQLite catalog path. Defaults to ~/.local/share/pixindex/index.sqlite.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Index pictures in a folder or S3 prefix."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = resolve_db_path(db)


@app.command()
def index(
    ctx: typer.Context,
    source: str = typer.Argument(help="Local folder or s3://bucket/prefix."),
) -> None:
    """Walk a local folder or S3 prefix and catalog images."""
    if source.startswith("s3://"):
        typer.echo("S3 is not implemented yet.", err=True)
        raise typer.Exit(code=1)

    path = Path(source).expanduser()
    if not path.exists():
        typer.echo(f"Not found: {path}", err=True)
        raise typer.Exit(code=1)

    try:
        result = index_local(path, ctx.obj["db"])
    except KeyboardInterrupt:
        typer.echo(
            "Stopped. Already saved rows stay in the catalog.",
            err=True,
        )
        raise typer.Exit(code=130) from None

    typer.echo(
        f"Indexed {result.indexed}, skipped {result.skipped}, failed {result.failed}."
    )


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
