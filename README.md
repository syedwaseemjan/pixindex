# pixindex

Index pictures in a folder or S3 prefix. Query the catalog. Export it.

```bash
pixindex index s3://bucket/shoots/2024/
pixindex stat
pixindex search --camera Nikon --has-gps
pixindex export csv
```

A CLI. No server, no queue, no daemon.
