# Picture search: how the code works

This is the technical path behind `embed`, word `search`, and `duplicates`. The user-facing commands are in the README.

## Embedding and vector

An **embedding** is what you get when a model reads an input and writes down a fixed list of numbers. That list is the **vector**.

pixindex uses CLIP, a model with two halves that share one number space:

| Half | fastembed model | Input | Output |
| --- | --- | --- | --- |
| Picture | `Qdrant/clip-ViT-B-32-vision` | the image pixels | 512 floats |
| Words | `Qdrant/clip-ViT-B-32-text` | the search text | 512 floats |

Both halves are stored under one id, `Qdrant/clip-ViT-B-32` (`MODEL_ID` in `src/pixindex/embedder.py`). A picture of a red tent and the words "red tent" land near each other in that space. A picture of a blue door lands somewhere else.

`ClipEmbedder.embed_image` and `ClipEmbedder.embed_text` are the only places that call the model. Everything else just stores those lists or compares them.

**Cosine similarity** is the score. It measures the angle between two vectors, from -1 to 1. Closer to 1 means more alike. `vectors.cosine` computes it in Python. fastembed already returns unit-length vectors. The formula still divides by the lengths, so a test double that does not normalize still ranks correctly.

There is no separate vector database. Each vector is a little-endian `float32` blob, 512 × 4 = 2048 bytes, in the `embeddings` table. At search time every candidate is scored in memory. That is exact, and it is enough for a personal catalog. An approximate index would be an optimization after the catalog is large, not a requirement for correct results.

## What is stored

`index` fills `images`. It stores the path, size, pixel size, camera, date, and GPS. It does not store a vector.

`embed` fills `embeddings`, one row per picture:

| Column | Role |
| --- | --- |
| `uri` | Same primary key as `images.uri` |
| `model_id` | Which CLIP pair produced `vector` |
| `vector` | The packed float list |
| `size`, `mtime_ns`, `etag` | Copy of the file fingerprint from `images` at the time of the embedding |
| `embedded_at` | When the row was written |

A row is fresh only when `model_id` is the current model and `size`, `mtime_ns`, and `etag` still match `images`. `db.fresh_embedding` checks that. A different model, or a file that has been re-indexed, is embedded again. Search joins on the same condition, so a stale vector is never ranked.

`duplicates` fills `picture_hashes`. That hash is not an embedding. See below.

When `db.upsert` rewrites an `images` row, it deletes that uri from `embeddings` and `picture_hashes` in the same transaction. Re-index means the file changed, so the derived rows are dropped and the next `embed` or `duplicates` rebuilds them.

## Command flow

```text
pixindex index
  cli.index
    index.index_source
      local: index.index_local
      s3:    index.index_s3
    metadata.read_metadata
    db.upsert
```

For a local file, skip the read when `size` and `mtime_ns` already match. For S3, skip when `etag` and `size` match. A JPEG on S3 is fetched with a range read of the first 64 KiB (`s3.JPEG_RANGE`), because EXIF usually sits in the header. PNG and WebP are fetched whole. This pass never asks CLIP for a vector.

```text
pixindex embed
  cli.embed
    embedder.load_embedder     # import fastembed, download on first use
    embed.embed_catalog
      db.fresh_embedding       # skip when model + fingerprint match
      pictures.open_picture    # full file, local or S3
      ClipEmbedder.embed_image
      vectors.pack_vector
      db.save_embedding
```

`open_picture` reads every byte. On S3 that is a full `GetObject` with no `Range` header. Before the read, a local file must still have the catalog's `size` and `mtime_ns`. If it does not, the file is counted as failed and the message says to run `index` again. The vector is not written from pixels the catalog does not describe.

One bad file does not stop the loop. `EmbedError` (the model is missing or failed to load) does stop it. The model is loaded once, before the loop, from `cli._embedder`.

Bytes counted in the summary are bytes actually read. A skipped picture adds nothing.

```text
pixindex search "red tent" --camera Nikon
  cli.search
    query.parse_filters
    embedder.load_embedder
    similar.search_pictures
      SQL: images that pass the filters
      LEFT JOIN embeddings for this model_id and fingerprint
      ClipEmbedder.embed_text
      vectors.unpack_vector + vectors.cosine
      sort by score descending, then uri
      keep --limit (default 20)
```

Filters run first, in SQL, through `query.where_clause`. The words only rank that set. The join is a `LEFT JOIN` inside `WHERE uri IN (SELECT ...)` so filter columns stay unambiguous, and pictures with no fresh vector come back with a null blob. Those are counted and omitted. The CLI prints the count and tells you to run `embed`.

Without search text, `cli.search` calls `query.search_uris` and prints paths in uri order. No model is loaded. `--limit` applies only to word search.

```text
pixindex duplicates
  cli.duplicates
    duplicates.find_duplicates
      db.fresh_hash
      pictures.open_picture
      dhash.dhash
      db.save_hash
      duplicates.group_hashes
```

## Copy grouping is not a vector search

`dhash.dhash` shrinks the picture to 9×8 grayscale pixels. Each pixel is compared with the one on its right: 8 rows × 8 comparisons = 64 bits, stored as 16 hex characters. `dhash.hamming` is the count of bits that differ.

`group_hashes` unions every pair whose distance is at most `--distance` (default 8, `DEFAULT_DISTANCE`). Groups of one are dropped. The comparison is O(n²) over 64-bit values, which is the right tradeoff for a personal catalog.

This fingerprint follows the light and dark layout. A smaller copy of the same shot usually matches. It does not place the picture in CLIP's number space, and word search does not read `picture_hashes`.

## Check

`pixindex check` calls `check.run_check`. That draws four example pictures in a temp directory, then runs `index_local`, `embed_catalog`, `search_pictures`, and `find_duplicates` against a temp catalog. The user's database is not opened.

The CLI passes `ClipEmbedder`. Tests pass `tests/color_embedder.py` `ColorEmbedder` instead. That double turns a picture into its average color and turns the words "red", "green", and "blue" into those colors. `pytest` can score the same pipeline without downloading CLIP. `pixindex check` is the run that uses the real model.

## Tests that lock the rules

| Test | Rule |
| --- | --- |
| `tests/test_embed.py` | Second run skips and reads 0 bytes. A changed `model_id` is rebuilt. Re-index deletes the vector. A file that changed on disk is not embedded. S3 embed uses one full GET. |
| `tests/test_similar.py` | Words rank the closer picture. Camera filters run before scoring. A vector from another `model_id` is ignored. |
| `tests/test_dhash.py` | A resized copy is within distance 8. A different shape is not. |
| `tests/test_duplicates.py` | Distance 0 groups only identical fingerprints. |
| `tests/test_check.py` | The built-in examples pass with `ColorEmbedder`. |
