# pixindex

pixindex looks through your pictures and writes down the useful facts about each one: size, camera, date, and whether the photo has a GPS location.

You run it in the terminal. It does not start a website, a queue, or a background service.

Right now it only works on pictures already on your computer. Amazon S3 and search are not ready yet.

## What it does today

Point it at a folder. It finds `.jpg`, `.jpeg`, `.png`, and `.webp` files.

For each picture it saves:

- the full path
- file size
- width and height
- camera make and model, if the file has that data
- when the photo was taken, if the file has that data
- GPS coordinates, if the file has them

That list is stored in a single SQLite file on your machine. Think of it as a notebook, not a photo library. pixindex does not move, copy, or change your pictures.

Hidden files (names that start with `.`) and folders that start with `.` are skipped.

## Install

You need Python 3.12 or newer.

On Ubuntu, if `python3.12 -m venv` fails, run `sudo apt install python3.12-venv` first.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
pixindex --help
```

## Use it

Index a folder and keep the notebook in the current directory:

```bash
pixindex --db ./catalog.sqlite index ./photos
```

Or index one picture:

```bash
pixindex --db ./catalog.sqlite index ./photos/beach.jpg
```

When it finishes you will see something like:

```text
Indexed 12, skipped 0, failed 0.
```

- **indexed** — new or changed pictures written to the notebook
- **skipped** — already in the notebook, and the file has not changed
- **failed** — not a readable image; pixindex prints the path and continues

If you press `Ctrl+C`, it stops. Pictures it already saved stay in the notebook. Run the same command again to continue. Unchanged files are skipped.

If you leave out `--db`, the notebook is stored at:

```text
~/.local/share/pixindex/index.sqlite
```

## Run it again

Same folder, same `--db`:

```bash
pixindex --db ./catalog.sqlite index ./photos
```

pixindex only re-reads a file if the size or the last-modified time changed. A large folder is slow the first time. Later runs are mostly a quick check.

## See a summary

Use the same `--db` as when you indexed:

```bash
pixindex --db ./catalog.sqlite stat
```

You get a short report: how many pictures, how much space they take, the date range, how many have GPS, and which cameras showed up.

To summarize only one folder you already indexed:

```bash
pixindex --db ./catalog.sqlite stat --source ./photos
```

If you have not indexed anything yet, stat tells you that and exits.

## What is not ready

These commands exist so you can see the plan, but they do not work yet:

```bash
pixindex search --camera Nikon --has-gps
pixindex export csv
pixindex index s3://my-bucket/photos/
```

## Tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
