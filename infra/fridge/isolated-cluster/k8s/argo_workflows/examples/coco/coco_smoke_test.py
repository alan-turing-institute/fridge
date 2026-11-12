import json
import os
import time
import zipfile
from pathlib import Path

import torch
import torchvision
from PIL import Image
from torchvision.transforms.functional import to_tensor
from torchvision.models.detection import maskrcnn_resnet50_fpn_v2

root = Path(os.environ.get("COCO_WORK_DIR", "/tmp/coco2017"))
root.mkdir(parents=True, exist_ok=True)

num_images = int(os.environ.get("COCO_NUM_IMAGES", "10"))
weights_path = os.environ.get("MODEL_WEIGHTS", "/work/model.pth")

print(f"PyTorch: {torch.__version__}", flush=True)
print(f"Torchvision: {torchvision.__version__}", flush=True)
print(f"ROCm: {torch.version.hip}", flush=True)
print(f"GPU available: {torch.cuda.is_available()}", flush=True)

if not torch.cuda.is_available():
    raise RuntimeError("No GPU available")

device = torch.device("cuda:0")
print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)

# Extract dataset from Argo input artifacts.
for filename in ("val2017.zip", "annotations_trainval2017.zip"):
    archive_path = Path("/work") / filename
    print(f"Extracting {filename}...", flush=True)

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(root)

# Load COCO metadata.
with (root / "annotations/instances_val2017.json").open() as f:
    coco = json.load(f)

images = sorted(coco["images"], key=lambda x: x["id"])
print(f"COCO validation images: {len(images)}", flush=True)

# Initialise model without downloading pretrained weights.
print("Loading Mask R-CNN...", flush=True)

model = maskrcnn_resnet50_fpn_v2(
    weights=None,
    weights_backbone=None,
    num_classes=91,
)

state_dict = torch.load(
    weights_path,
    map_location="cpu",
    weights_only=True,
)

model.load_state_dict(state_dict)
model = model.to(device).eval()

print("Model loaded successfully", flush=True)

# Run a small inference smoke test.
results = []

torch.cuda.synchronize()
start = time.monotonic()

with torch.inference_mode():
    for i, image_info in enumerate(images[:num_images]):
        image_path = root / "val2017" / image_info["file_name"]

        with Image.open(image_path) as img:
            image = to_tensor(img.convert("RGB")).to(device)

        prediction = model([image])[0]

        # Ensure the prediction has completed.
        scores = prediction["scores"].cpu()
        labels = prediction["labels"].cpu()
        boxes = prediction["boxes"].cpu()

        selected = scores >= 0.5

        result = {
            "image_id": image_info["id"],
            "detections": int(selected.sum().item()),
            "scores": scores[selected].tolist(),
            "labels": labels[selected].tolist(),
            "boxes": boxes[selected].tolist(),
        }

        results.append(result)

        print(
            f"Image {i + 1}/{num_images}: "
            f"{result['detections']} detections "
            f"(score >= 0.5)",
            flush=True,
        )

torch.cuda.synchronize()
elapsed = time.monotonic() - start

# Save predictions locally.
output = Path("/tmp/coco-predictions.json")
with output.open("w") as f:
    json.dump(results, f, indent=2)

print("\n=== RESULTS ===", flush=True)
print(f"Images processed: {len(results)}")
print(f"Elapsed: {elapsed:.2f} seconds")
print(f"Images/sec: {len(results) / elapsed:.2f}")
print(f"Peak GPU memory: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")
print(f"Predictions saved to: {output}")
print("SUCCESS")
