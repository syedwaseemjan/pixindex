from pixindex.metadata import gps_degrees


def test_gps_degrees_north_east() -> None:
    lat = gps_degrees((33, 43, 12), "N")
    lon = gps_degrees((73, 4, 0), "E")
    assert lat is not None and lon is not None
    assert round(lat, 4) == 33.72
    assert round(lon, 4) == 73.0667


def test_gps_degrees_south_west() -> None:
    lat = gps_degrees((10, 0, 0), "S")
    lon = gps_degrees((20, 0, 0), "W")
    assert lat == -10
    assert lon == -20
