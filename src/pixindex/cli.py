from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer

from pixindex import __version__
from pixindex.db import connect, resolve_db_path
from pixindex.embed import embed_catalog, format_embed_result
from pixindex.embedder import EmbedError, load_embedder
from pixindex.export import parse_format, render_export, search_rows
from pixindex.index import IndexSourceError, index_source
from pixindex.query import QueryError, parse_filters, search_uris
from pixindex.stat import catalog_stats, format_stats

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
    try:
        result = index_source(source, ctx.obj["db"])
    except IndexSourceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
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
def embed(
    ctx: typer.Context,
    source: str | None = typer.Option(None, help="Limit to one indexed folder."),
) -> None:
    """Read pictures and save what they show, for word search."""
    filters = _filters(source=source)
    _require_catalog(ctx)
    embedder = _embedder()
    try:
        result = embed_catalog(ctx.obj["db"], embedder, filters)
    except KeyboardInterrupt:
        _stopped()
    typer.echo(format_embed_result(result, embedder.model_id))


@app.command()
def search(
    ctx: typer.Context,
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
    source: str | None = typer.Option(None, help="Limit to one indexed folder."),
) -> None:
    """Filter the catalog and print matching paths."""
    filters = _filters(
        source=source,
        camera=camera,
        after=after,
        before=before,
        has_gps=has_gps,
        ext=ext,
        min_size=min_size,
    )
    conn = _open_catalog(ctx)
    try:
        for uri in search_uris(conn, filters):
            typer.echo(uri)
    finally:
        conn.close()


@app.command()
def stat(
    ctx: typer.Context,
    source: str | None = typer.Option(
        None, help="Limit the summary to one indexed folder."
    ),
) -> None:
    """Print a summary of the catalog."""
    conn = _open_catalog(ctx)
    try:
        typer.echo(format_stats(catalog_stats(conn, _filters(source=source))))
    finally:
        conn.close()


@app.command()
def export(
    ctx: typer.Context,
    output_format: str = typer.Argument(help="csv or json.", metavar="FORMAT"),
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
    source: str | None = typer.Option(None, help="Limit to one indexed folder."),
) -> None:
    """Write matching rows to csv or json."""
    try:
        fmt = parse_format(output_format)
    except QueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    filters = _filters(
        source=source,
        camera=camera,
        after=after,
        before=before,
        has_gps=has_gps,
        ext=ext,
        min_size=min_size,
    )
    conn = _open_catalog(ctx)
    try:
        body = render_export(search_rows(conn, filters), fmt)
    finally:
        conn.close()
    typer.echo(body, nl=False)


def _embedder():
    try:
        return load_embedder()
    except EmbedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _stopped() -> NoReturn:
    typer.echo(
        "Stopped. Already saved rows stay in the catalog.",
        err=True,
    )
    raise typer.Exit(code=130) from None


def _require_catalog(ctx: typer.Context) -> None:
    db_path = ctx.obj["db"]
    if not db_path.is_file():
        typer.echo(
            f"No catalog at {db_path}. Run pixindex index first.",
            err=True,
        )
        raise typer.Exit(code=1)


def _open_catalog(ctx: typer.Context):
    _require_catalog(ctx)
    return connect(ctx.obj["db"])


def _filters(**kwargs):
    try:
        return parse_filters(**kwargs)
    except QueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
