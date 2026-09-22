# pixindex

[![Tests](https://github.com/syedwaseemjan/pixindex/actions/workflows/tests.yml/badge.svg)](https://github.com/syedwaseemjan/pixindex/actions/workflows/tests.yml)

Index pictures in a folder or in an Amazon S3 bucket. Search the catalog. Export it.

pixindex is a command-line tool. It does not start a server. It does not run in the background. It does not move, copy, or change your pictures.

```bash
pipx install pixindex

pixindex --db ./catalog.sqlite index ./photos
pixindex --db ./catalog.sqlite stat
pixindex --db ./catalog.sqlite search --camera Nikon --has-gps
pixindex --db ./catalog.sqlite export csv > inventory.csv
```

## What it records

It finds `.jpg`, `.jpeg`, `.png`, and `.webp` files. Files and folders whose names start with `.` are skipped. HEIC and RAW files are not supported.

For each picture it stores:

- the full path, or an S3 location like `s3://bucket/key`
- file size, width, and height
- camera make and model, if the picture has that information
- date taken, if the picture has that information
- GPS coordinates, if the picture has that information

This information is stored in a SQLite file on your computer. pixindex does not store the pictures themselves.

If you do not pass `--db`, the catalog file is:

```text
~/.local/share/pixindex/index.sqlite
```

## Install

You need Python 3.12 or newer.

```bash
pipx install pixindex
pixindex --help
```

Or with pip:

```bash
pip install pixindex
```

## Index

You can index a folder, a single file, or a location in an S3 bucket:

```bash
pixindex --db ./catalog.sqlite index ./photos
pixindex --db ./catalog.sqlite index ./photos/beach.jpg
pixindex --db ./catalog.sqlite index s3://my-bucket/photos/2024/
```

S3 uses your normal AWS credentials. Set `AWS_PROFILE` or `AWS_ACCESS_KEY_ID` the same way you would for other AWS tools. pixindex does not change files in the bucket. For JPEG files, it only downloads the start of the file, which is enough to read the metadata. For PNG and WebP files, it downloads the whole file.

When it finishes:

```text
Indexed 12, skipped 0, failed 0.
```

- **indexed** — the picture was new, or it changed, so it was written to the catalog
- **skipped** — the picture is already in the catalog, and the file has not changed
- **failed** — the picture could not be read; pixindex prints the path and continues with the next file

Press Ctrl+C to stop. Pictures that were already saved stay in the catalog. If you run the same command again, files that have not changed are skipped. For photos on your computer, pixindex compares the file size and the last time the file was changed. For photos on S3, it compares the ETag. The ETag is a fingerprint that Amazon stores for each object.

The first run over a large folder or S3 location can take a while. Later runs are faster, because most files are only checked to see if they changed.

If AWS credentials are missing, or the bucket cannot be listed, pixindex prints an error and exits.

## Stat

```bash
pixindex --db ./catalog.sqlite stat
pixindex --db ./catalog.sqlite stat --source ./photos
```

This prints counts, total size, the date range, how many pictures have GPS, and which cameras appear in the catalog. If the catalog file does not exist yet, stat prints an error and exits.

## Search

Each matching picture is printed as one path per line. A picture must match every option you pass.

```bash
pixindex --db ./catalog.sqlite search --camera Nikon --has-gps
pixindex --db ./catalog.sqlite search --after 2024-06-01 --before 2024-08-31
pixindex --db ./catalog.sqlite search --ext jpg --min-size 5mb
pixindex --db ./catalog.sqlite search --source ./photos --no-gps
pixindex --db ./catalog.sqlite search --source s3://my-bucket/photos/2024
```

- `--camera` — camera make or model contains this text
- `--after` / `--before` — date the picture was taken, in `YYYY-MM-DD` format. Both days are included. Pictures with no date are left out
- `--has-gps` / `--no-gps` — only pictures that have a location, or only pictures that do not
- `--ext` — file type (`jpg` also matches `.jpeg`)
- `--min-size` — smallest file size to include, for example `5mb`
- `--source` — only pictures from one folder or S3 location you already indexed

If nothing matches, nothing is printed. If you pass a date or size that pixindex cannot read, it prints an error and exits.

## Export

Export uses the same filters as search. Results are printed in the terminal. To save them to a file, use `>` as in the examples below.

```bash
pixindex --db ./catalog.sqlite export csv > inventory.csv
pixindex --db ./catalog.sqlite export json > inventory.json
pixindex --db ./catalog.sqlite export csv --camera Nikon --has-gps > nikon-gps.csv
```

Use `csv` if you want to open the file in a spreadsheet. Use `json` if you want to read it from a script. The columns are path, folder, size, width, height, date taken, camera, and GPS.

If no pictures match, the export is still valid. CSV will contain only the header row. JSON will be an empty list: `[]`. The format must be `csv` or `json`.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

On Ubuntu, if `python3.12 -m venv` fails, run `sudo apt install python3.12-venv`.

## License

MIT
