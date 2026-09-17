# pixindex

Index pictures in a folder or S3 prefix. Query the catalog. Export it.

```bash
pixindex index s3://bucket/shoots/2024/
pixindex stat
pixindex search --camera Nikon --has-gps
pixindex export csv
```

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
