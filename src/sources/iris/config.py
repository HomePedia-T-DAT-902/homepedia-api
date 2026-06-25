from pathlib import Path

RAW_DIR = Path("data/raw/iris")
DEST_FILE = "contours-iris.geojson"

WFS_BASE = "https://data.geopf.fr/wfs/ows"
WFS_LAYER = "STATISTICALUNITS.IRIS:contours_iris"
PAGE_SIZE = 5_000

BATCH_SIZE = 5_000
