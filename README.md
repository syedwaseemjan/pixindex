# pixindex

Index pictures in a folder or an S3 prefix. Search the catalog. Export it.

A CLI. No server, no queue, no daemon. It does not move, copy, or change your pictures.

```bash
pipx install pixindex

pixindex --db ./catalog.sqlite index ./photos
pixindex --db ./catalog.sqlite stat
pixindex --db ./catalog.sqlite search --camera Nikon --has-gps
pixindex --db ./catalog.sqlite export csv > inventory.csv
```

## What it records

It finds `.jpg`, `.jpeg`, `.png`, and `.webp` files. Hidden files and folders (names that start with `.`) are skipped. HEIC and RAW are not supported.

For each picture it stores:

- the full path, or `s3://bucket/key`
- file size, width, and height
- camera make and model, if present
- date taken, if present
- GPS coordinates, if present

That list lives in a SQLite file on your machine. It is a notebook, not a photo library.

If you omit `--db`, the notebook is:

```text
~/.local/share/pixindex/index.sqlite
```

## Install

Python 3.12 or newer.

```bash
pipx install pixindex
pixindex --help
```

Or with pip:

```bash
pip install pixindex
```

## Index

A folder, one file, or an S3 prefix:

```bash
pixindex --db ./catalog.sqlite index ./photos
pixindex --db ./catalog.sqlite index ./photos/beach.jpg
pixindex --db ./catalog.sqlite index s3://my-bucket/photos/2024/
```

S3 uses your normal AWS credentials (`AWS_PROFILE` or `AWS_ACCESS_KEY_ID`). Objects in the bucket are not changed. JPEGs are read from the start of the object only, enough for metadata. PNG and WebP are downloaded in full.

When it finishes:

```text
Indexed 12, skipped 0, failed 0.
```

- **indexed** — new or changed pictures written to the notebook
- **skipped** — already there, and the file has not changed
- **failed** — not readable; pixindex prints the path and continues

`Ctrl+C` stops the run. Rows already saved stay. Run the same command again; unchanged files are skipped. Local files skip on size and last-modified time. S3 objects skip on ETag.

A first run over a large folder or prefix can take a while. Later runs are mostly a check.

If AWS credentials are missing, or the bucket cannot be listed, pixindex says so and exits.

## Stat

```bash
pixindex --db ./catalog.sqlite stat
pixindex --db ./catalog.sqlite stat --source ./photos
```

You get counts, total size, date range, how many have GPS, and which cameras showed up. If the catalog does not exist yet, stat says so and exits.

## Search

One path per line. A picture must match every flag you pass.

```bash
pixindex --db ./catalog.sqlite search --camera Nikon --has-gps
pixindex --db ./catalog.sqlite search --after 2024-06-01 --before 2024-08-31
pixindex --db ./catalog.sqlite search --ext jpg --min-size 5mb
pixindex --db ./catalog.sqlite search --source ./photos --no-gps
pixindex --db ./catalog.sqlite search --source s3://my-bucket/photos/2024
```

- `--camera` — make or model contains this text
- `--after` / `--before` — date taken, `YYYY-MM-DD`. Both days are included. Pictures with no date are left out
- `--has-gps` / `--no-gps` — has a location, or does not
- `--ext` — file type (`jpg` also matches `.jpeg`)
- `--min-size` — smallest file, for example `5mb`
- `--source` — only one folder or S3 prefix you already indexed

No matches means no output. A bad date or size is an error.

## Export

Same filters as search. Prints to the terminal; redirect to keep a file.

```bash
pixindex --db ./catalog.sqlite export csv > inventory.csv
pixindex --db ./catalog.sqlite export json > inventory.json
pixindex --db ./catalog.sqlite export csv --camera Nikon --has-gps > nikon-gps.csv
```

`csv` is for a spreadsheet. `json` is for a script. Columns are path, folder, size, width, height, date taken, camera, and GPS.

An empty result is still valid: CSV is only the header, JSON is `[]`. Format must be `csv` or `json`.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Ubuntu, if `python3.12 -m venv` fails: `sudo apt install python3.12-venv`.

## License

MIT
