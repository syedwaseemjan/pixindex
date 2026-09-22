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

This prints counts, total size, the date range, how many pictures have GPS, and which cameras appear in the catalog. `--source` prints the same summary for one folder or S3 location you already indexed.

```text
3 pictures
4.9 KB

Taken: 2024-03-12 to 2024-11-02
With GPS: 1 of 3 (33%)

Cameras
  Canon EOS R6     2
  Apple iPhone 15  1
```

Dates are the earliest and latest day a picture was taken. A picture with no camera is listed as `unknown`. If the catalog has no pictures, stat prints `No pictures in the catalog yet.` If the catalog file does not exist yet, stat prints an error and exits.

## Search

Each matching picture is printed as one path per line. A picture must match every option you pass.

```bash
pixindex --db ./catalog.sqlite search --camera Nikon --has-gps
pixindex --db ./catalog.sqlite search --after 2024-06-01 --before 2024-08-31
pixindex --db ./catalog.sqlite search --ext jpg --min-size 5mb
pixindex --db ./catalog.sqlite search --source ./photos --no-gps
pixindex --db ./catalog.sqlite search --source s3://my-bucket/photos/2024
```

Paths on your computer are absolute. S3 pictures are printed as `s3://` locations.

```text
/photos/beach.jpg
/photos/2024/pier.jpg
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

Use `csv` if you want to open the file in a spreadsheet. Use `json` if you want to read it from a script. One CSV row looks like this:

```text
uri,source,size,width,height,captured_at,camera_make,camera_model,has_gps,gps_lat,gps_lon
/photos/beach.jpg,/photos,2400000,6000,4000,2024-07-14T15:02:11,Nikon,Z 6,true,33.6844,73.0479
```

The same picture as JSON:

```json
[
  {
    "uri": "/photos/beach.jpg",
    "source": "/photos",
    "size": 2400000,
    "width": 6000,
    "height": 4000,
    "captured_at": "2024-07-14T15:02:11",
    "camera_make": "Nikon",
    "camera_model": "Z 6",
    "has_gps": true,
    "gps_lat": 33.6844,
    "gps_lon": 73.0479
  }
]
```

`uri` is the picture. `source` is the folder or S3 location you indexed. Missing metadata is an empty CSV cell, or `null` in JSON. If no pictures match, the export is still valid. CSV will contain only the header row. JSON will be an empty list: `[]`. The format must be `csv` or `json`.

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
