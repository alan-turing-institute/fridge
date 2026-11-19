import json
import os
import time
import zipfile
from pathlib import Path

import numpy as np
import torch
import torchvision
from PIL import Image
from torchvision.transforms.functional import to_tensor
from torchvision.models.detection import maskrcnn_resnet50_fpn_v2
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from pycocotools import mask as mask_utils


# Configuration
root = Path(os.getenv("COCO_WORK_DIR", "/tmp/coco2017"))
num_images = int(os.getenv("COCO_NUM_IMAGES", "5000"))
weights_path = os.getenv("MODEL_WEIGHTS", "/work/model.pth")
output_dir = Path("/tmp")

root.mkdir(parents=True, exist_ok=True)

print("=== Environment ===", flush=True)
print(f"PyTorch: {torch.__version__}")
print(f"Torchvision: {torchvision.__version__}")
print(f"ROCm: {torch.version.hip}")
print(f"GPU available: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    raise RuntimeError("No GPU available")

device = torch.device("cuda:0")
torch.cuda.set_device(device)
print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)


# Extract COCO validation dataset
for filename in ("val2017.zip", "annotations_trainval2017.zip"):
    path = Path("/work") / filename
    print(f"Extracting {filename}...", flush=True)

    with zipfile.ZipFile(path) as archive:
        archive.extractall(root)


# Load ground truth annotations
annotation_path = root / "annotations/instances_val2017.json"
coco_gt = COCO(str(annotation_path))

image_ids = sorted(coco_gt.getImgIds())
image_ids = image_ids[:num_images]

print(f"Evaluating {len(image_ids)} images", flush=True)


# Load pretrained Mask R-CNN
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


# Run inference
bbox_results = []
segm_results = []

torch.cuda.reset_peak_memory_stats()
start = time.monotonic()

with torch.inference_mode():
    for i, image_id in enumerate(image_ids):
        info = coco_gt.loadImgs([image_id])[0]
        image_path = root / "val2017" / info["file_name"]

        with Image.open(image_path) as img:
            image = to_tensor(img.convert("RGB")).to(device)

        prediction = model([image])[0]

        # Transfer predictions to CPU
        boxes = prediction["boxes"].cpu().numpy()
        scores = prediction["scores"].cpu().numpy()
        labels = prediction["labels"].cpu().numpy()
        masks = prediction["masks"].cpu().numpy()

        for box, score, label, mask in zip(boxes, scores, labels, masks):
            x1, y1, x2, y2 = box.tolist()

            # COCO expects XYWH, not XYXY.
            bbox_results.append(
                {
                    "image_id": int(image_id),
                    "category_id": int(label),
                    "bbox": [
                        float(x1),
                        float(y1),
                        float(x2 - x1),
                        float(y2 - y1),
                    ],
                    "score": float(score),
                }
            )

            # Convert predicted mask to COCO RLE.
            binary_mask = np.asfortranarray((mask[0] > 0.5).astype(np.uint8))

            rle = mask_utils.encode(binary_mask)
            rle["counts"] = rle["counts"].decode("utf-8")

            segm_results.append(
                {
                    "image_id": int(image_id),
                    "category_id": int(label),
                    "segmentation": rle,
                    "score": float(score),
                }
            )

        if (i + 1) % 50 == 0 or i + 1 == len(image_ids):
            torch.cuda.synchronize()
            elapsed = time.monotonic() - start
            print(
                f"Processed {i + 1}/{len(image_ids)} images, {elapsed:.1f}s elapsed",
                flush=True,
            )

torch.cuda.synchronize()
inference_time = time.monotonic() - start

print("Inference complete", flush=True)
print(f"Images/sec: {len(image_ids) / inference_time:.2f}")

# Save predictions
bbox_path = output_dir / "coco-bbox.json"
segm_path = output_dir / "coco-segm.json"

bbox_path.write_text(json.dumps(bbox_results))
segm_path.write_text(json.dumps(segm_results))


# Run COCO evaluation
metrics = {}

for eval_type, result_path in (
    ("bbox", bbox_path),
    ("segm", segm_path),
):
    print(f"\n=== COCO {eval_type} evaluation ===", flush=True)

    if not json.loads(result_path.read_text()):
        raise RuntimeError(f"No {eval_type} detections produced")

    coco_dt = coco_gt.loadRes(str(result_path))

    evaluator = COCOeval(coco_gt, coco_dt, eval_type)
    evaluator.params.imgIds = image_ids
    evaluator.evaluate()
    evaluator.accumulate()
    evaluator.summarize()

    metrics[eval_type] = {
        "mAP": float(evaluator.stats[0]),
        "AP50": float(evaluator.stats[1]),
        "AP75": float(evaluator.stats[2]),
        "AP_small": float(evaluator.stats[3]),
        "AP_medium": float(evaluator.stats[4]),
        "AP_large": float(evaluator.stats[5]),
    }


# Save evaluation summary
summary = {
    "model": "maskrcnn_resnet50_fpn_v2",
    "dataset": "COCO val2017",
    "images_evaluated": len(image_ids),
    "gpu": torch.cuda.get_device_name(0),
    "pytorch": torch.__version__,
    "torchvision": torchvision.__version__,
    "rocm": torch.version.hip,
    "inference_seconds": inference_time,
    "images_per_second": len(image_ids) / inference_time,
    "peak_gpu_memory_gib": (torch.cuda.max_memory_allocated() / 2**30),
    "metrics": metrics,
}

summary_path = output_dir / "coco-summary.json"
summary_path.write_text(json.dumps(summary, indent=2))

print("\n=== FINAL SUMMARY ===")
print(json.dumps(summary, indent=2))
print("SUCCESS")
