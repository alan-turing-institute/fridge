import json
import time
import zipfile
from pathlib import Path

root = Path("/work")
dataset = Path("/tmp/coco2017")
dataset.mkdir(parents=True, exist_ok=True)

for filename in ("val2017.zip", "annotations_trainval2017.zip"):
    archive_path = root / filename

    print(f"Extracting {filename}", flush=True)
    start = time.monotonic()

    with zipfile.ZipFile(archive_path) as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"Corrupt archive member: {bad_file}")
        archive.extractall(dataset)

    elapsed = time.monotonic() - start
    print(f"Extracted {filename} in {elapsed:.1f}s", flush=True)

# Validate COCO annotations
annotations_path = dataset / "annotations/instances_val2017.json"

with annotations_path.open() as f:
    annotations = json.load(f)

images = annotations["images"]
image_ids = {image["id"] for image in images}

assert len(images) == 5000, f"Expected 5000 images, got {len(images)}"

missing = [
    image["file_name"]
    for image in images
    if not (dataset / "val2017" / image["file_name"]).is_file()
]

if missing:
    raise RuntimeError(f"Missing images: {missing[:5]}")

for annotation in annotations["annotations"]:
    if annotation["image_id"] not in image_ids:
        raise RuntimeError(
            f"Annotation references unknown image: {annotation['image_id']}"
        )

print("\nCOCO validation dataset ready", flush=True)
print(f"Images: {len(images)}")
print(f"Annotations: {len(annotations['annotations'])}")
print(f"Categories: {len(annotations['categories'])}")
print("SUCCESS")
