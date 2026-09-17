# pixindex

Index pictures in a folder or S3 prefix. Query the catalog. Export it.

```bash
pixindex --db ./catalog.sqlite index ./photos
pixindex stat
pixindex search --camera Nikon --has-gps
pixindex export csv
```

`index` works on a local folder or a single image. JPEG, PNG, and WebP. Unchanged files are skipped on the next run. S3 is not implemented yet.

A CLI. No server, no queue, no daemon.

## Requirements

Python 3.12 or newer.

## Install from source

On Ubuntu, install `python3.12-venv` first if `python3.12 -m venv` fails.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pixindex --help
```
