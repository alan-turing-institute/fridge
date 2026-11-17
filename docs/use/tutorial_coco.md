---
downloads:
  - url: ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/prepare.py
    title: prepare.py
    filename: prepare.py
  - url: ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_smoke_test.py
    title: coco_smoke_test.py
    filename: coco_smoke_test.py
  - url: ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_evaluate.py
    title: coco_evaluate.py
    filename: coco_evaluate.py
  - url: ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_prepare.yaml
    title: coco_prepare.yaml
    filename: coco_prepare.yaml
  - url: ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_smoke_test.yaml
    title: coco_smoke_test.yaml
    filename: coco_smoke_test.yaml
  - url: ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_evaluate.yaml
    title: coco_evaluate.yaml
    filename: coco_evaluate.yaml
---

(use-tutorial-coco)=
# Tutorial: Evaluating an Object Detection Model on COCO

This tutorial walks through a complete GPU job on a FRIDGE.
You will evaluate a pretrained [Mask R-CNN](https://pytorch.org/vision/stable/models/mask_rcnn.html) model on the [COCO](https://cocodataset.org/) 2017 validation set, and download the evaluation results.

The job is built up in three stages, each its own workflow template:

1. **`coco-prepare`** checks that the dataset arrived intact, using only a CPU.
2. **`coco-smoke-test`** loads the model on a GPU and runs it on a handful of images.
3. **`coco-evaluate`** runs the model on all 5,000 images and scores it with the official COCO evaluation code.

Each stage tests a little more than the one before.
If something is wrong, such as a corrupt upload, a missing GPU or a missing Python package, you find out from a short job rather than from a long one.

Along the way the tutorial shows how to deal with the main constraints of a FRIDGE:

- workflow pods have no internet access, so the dataset, the model weights and any extra Python packages must all be uploaded
- input data arrives through the `ingress` bucket and results leave through the `egress` bucket
- GPUs must be requested explicitly

It assumes you have read [Using the FRIDGE API](./api.md) and can reach the API.
The templates request AMD GPUs, as on Zenith; for other clusters, see [Adapting the templates](#use-tutorial-coco-adapting).

(use-tutorial-coco-files)=
## Who does what

Workflow templates can only be deployed by a {term}`TRE Administrator`, as described in [Creating Workflow Templates](../deploy/workflow_templates.md).
Everything else in this tutorial is done by a {term}`Job Submitter` through the API.

The files used here can be downloaded from the **Download** menu at the top of this page:

| Stage | Template | Script |
| --- | --- | --- |
| 1 | `coco_prepare.yaml` | `prepare.py` |
| 2 | `coco_smoke_test.yaml` | `coco_smoke_test.py` |
| 3 | `coco_evaluate.yaml` | `coco_evaluate.py` |

They are also in the [FRIDGE repository](https://github.com/alan-turing-institute/fridge/tree/main/infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco).
Job Submitters only need the three scripts; the templates are for TRE Administrators.

The scripts are uploaded as input data alongside the dataset, rather than baked into the templates.
This lets you change a script without asking for the template to be redeployed.

### Deploying the templates

A TRE Administrator deploys the three templates against the isolated cluster:

```console
cd infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco
kubectl --context <isolated-cluster-context> apply -f coco_prepare.yaml
kubectl --context <isolated-cluster-context> apply -f coco_smoke_test.yaml
kubectl --context <isolated-cluster-context> apply -f coco_evaluate.yaml
```

Check that they are visible through the API:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflowtemplates/argo-workflows"
```

## Gathering the inputs

Download everything the job needs on a machine with internet access.
None of it can be downloaded from inside the FRIDGE.

| Object | Source | Size |
| --- | --- | --- |
| `val2017.zip` | <http://images.cocodataset.org/zips/val2017.zip> | 778 MB |
| `annotations_trainval2017.zip` | <http://images.cocodataset.org/annotations/annotations_trainval2017.zip> | 241 MB |
| `maskrcnn_resnet50_fpn_v2_coco-73cbd019.pth` | <https://download.pytorch.org/models/maskrcnn_resnet50_fpn_v2_coco-73cbd019.pth> | 176 MB |
| `pycocotools-2.0.11-cp312-abi3-…whl` | PyPI, see below | < 1 MB |

```console
curl -LO http://images.cocodataset.org/zips/val2017.zip
curl -LO http://images.cocodataset.org/annotations/annotations_trainval2017.zip
curl -LO https://download.pytorch.org/models/maskrcnn_resnet50_fpn_v2_coco-73cbd019.pth
```

The evaluation stage needs [`pycocotools`](https://pypi.org/project/pycocotools/), which is not in the PyTorch image.
Download the Linux wheel that matches the image, whatever platform you are downloading from:

```console
pip download pycocotools==2.0.11 \
  --only-binary=:all: \
  --no-deps \
  --platform manylinux_2_28_x86_64 \
  --python-version 3.12 \
  --dest .
```

The `abi3` in the wheel's name means it works with any Python from 3.12 onwards, including the Python 3.14 in the image.
It must be the exact file name used in `coco_evaluate.yaml`; if pip fetches a different build, update the template to match.

Finally, download the three scripts, either from the Download menu at the top of this page or with:

```console
base=https://raw.githubusercontent.com/alan-turing-institute/fridge/main/infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco
for f in prepare.py coco_smoke_test.py coco_evaluate.py; do
  curl -LO "$base/$f"
done
```

### Uploading

Upload the data, the weights, the wheel and the three scripts to the `ingress` bucket:

```console
for f in val2017.zip annotations_trainval2017.zip \
         maskrcnn_resnet50_fpn_v2_coco-73cbd019.pth \
         pycocotools-2.0.11-cp312-abi3-*.whl \
         prepare.py coco_smoke_test.py coco_evaluate.py; do
  curl -k -u "$FRIDGE_AUTH" -F "file=@$f" "$FRIDGE_URL/object/ingress/upload"
done
```

The templates look for each object by its exact name.
If a file was saved under a different name, rename it first, or give the name in the upload, for example `-F "file=@prepare-1a2b3c.py;filename=prepare.py"`.

Then check that all seven objects are there:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/object/list?bucket=ingress"
```

The templates read these objects directly from object storage as [input artifacts](#use-api-artifacts), so you do not need to copy them to the shared volume with `/object/move`.

## Stage 1: Check the dataset

The first stage runs on a CPU, in a small stock Python image.
It unpacks both archives and checks that:

- neither archive is corrupt
- the annotations describe exactly 5,000 images
- every image named in the annotations is present
- every annotation refers to a known image

This catches truncated or partial uploads before any GPU time is spent.

```{literalinclude} ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_prepare.yaml
:language: yaml
```

Each entry under `inputs.artifacts` gives an object `key` in the `ingress` bucket and the `path` where Argo places it before the container starts.
No other S3 settings are needed, because `ingress` is Argo's default artifact repository.

The archives are unpacked to `/tmp`, which is backed by the node's local disk.
The `ephemeral-storage` request makes sure the pod lands on a node with room for both the archives and their contents.

Submit the workflow.
This template has no parameters:

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  -H "Content-Type: application/json" \
  -d '{"namespace": "argo-workflows", "template_name": "coco-prepare", "parameters": []}' \
  "$FRIDGE_URL/workflowevents/from_template/"
```

Note the workflow name in the response, such as `coco-prepare-abcde`, and check its status until it reaches `Succeeded`:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflows/argo-workflows/coco-prepare-abcde"
```

Its log should end like this:

```console
curl -k -u "$FRIDGE_AUTH" "$FRIDGE_URL/workflows/argo-workflows/coco-prepare-abcde/log"
```

```text
COCO validation dataset ready
Images: 5000
Annotations: 36781
Categories: 80
SUCCESS
```

## Stage 2: Smoke test on a GPU

The second stage checks that the GPU is usable and that the model loads and produces sensible output, by running it on a few images.
Its script, `coco_smoke_test.py`:

1. prints the PyTorch, Torchvision and ROCm versions, and fails if no GPU is visible
2. unpacks the dataset
3. builds Mask R-CNN and loads the uploaded weights
4. runs it on the first `COCO_NUM_IMAGES` images, keeping detections with a score of at least 0.5
5. writes the detections to `/tmp/coco-predictions.json`

The model is created with `weights=None` and `weights_backbone=None`, and the weights are then loaded from the uploaded file:

```python
model = maskrcnn_resnet50_fpn_v2(weights=None, weights_backbone=None, num_classes=91)
model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
```

Asking Torchvision for pretrained weights, for example with `weights="DEFAULT"`, would make it try to download them, which fails without internet access.

```{literalinclude} ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_smoke_test.yaml
:language: yaml
```

Compared with stage 1, this template adds:

The GPU
: `amd.com/gpu: 1` under `resources.limits`, and the GPU device group `992` under `spec.securityContext.supplementalGroups`. Without both, the container cannot use the GPU, and the script stops with `No GPU available`.

A parameter
: `num-images`, defaulting to `10`, sets how many images to run. It reaches the script as the `COCO_NUM_IMAGES` environment variable rather than being substituted into a command, so a Job Submitter cannot use it to inject commands.

An output artifact
: After the container exits, Argo uploads `/tmp/coco-predictions.json` to the `egress` bucket. Because `egress` is not the default artifact repository, the artifact gives the full S3 configuration. `archive: none` stores the file as it is, instead of as a `.tgz` archive.

The output key includes `{{workflow.name}}`, so each run writes to its own prefix and you can find its results from the name the API gives you when you submit it.

Submit it, optionally setting the number of images:

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  -H "Content-Type: application/json" \
  -d '{
        "namespace": "argo-workflows",
        "template_name": "coco-smoke-test",
        "parameters": [{"name": "num-images", "value": "10"}]
      }' \
  "$FRIDGE_URL/workflowevents/from_template/"
```

The log should show the GPU, a line per image and a short summary:

```text
GPU available: True
GPU: AMD Instinct MI355X
...
Image 10/10: 4 detections (score >= 0.5)

=== RESULTS ===
Images processed: 10
...
SUCCESS
```

Most images should have at least one detection.
If every image has none, the weights have probably not loaded correctly.

When the workflow has succeeded, download the predictions:

```console
curl -k -u "$FRIDGE_AUTH" -OJ \
  "$FRIDGE_URL/object/egress/experiments/coco/coco-smoke-test-abcde/predictions.json"
```

## Stage 3: Full evaluation

The last stage runs the model on all 5,000 validation images and scores its boxes and masks with the COCO evaluation code from `pycocotools`.

### Installing a package without internet access

`pycocotools` is not in the PyTorch image, and the pod cannot reach PyPI.
Instead, the wheel you uploaded is fetched as an input artifact, and the container installs it from the local file before running the script:

```bash
python3 -m pip install --no-index --no-deps --no-cache-dir \
  --target /tmp/python-deps /work/wheels/*.whl
export PYTHONPATH="/tmp/python-deps:${PYTHONPATH:-}"
```

`--no-index` stops pip from trying to reach PyPI.
`--target /tmp/python-deps` is needed because the container runs as a non-root user and cannot write to the image's own `site-packages`.
`pycocotools` only needs NumPy, which the image already has, so `--no-deps` is safe; a package with dependencies that are not in the image needs their wheels uploaded too.

The alternative is to build an image with the package already installed, for example:

```dockerfile
FROM rocm/pytorch:rocm10.1.0_ubuntu26.04_py3.14_pytorch_release_2.14.0
RUN python3 -m pip install --no-cache-dir pycocotools
```

The image must then be pushed to one of the registries the FRIDGE can pull from, such as `ghcr.io`, and the template changed to use it.
That is better for packages used by many templates, while uploading a wheel suits a one-off job.

### The template

```{literalinclude} ../../infra/fridge/isolated-cluster/k8s/argo_workflows/examples/coco/coco_evaluate.yaml
:language: yaml
```

Its script, `coco_evaluate.py`, runs the model on each image and converts the results to COCO's format: boxes from corner coordinates to `[x, y, width, height]`, and masks to run-length encoding.
It then runs `COCOeval` for both boxes (`bbox`) and masks (`segm`), and writes three files, each uploaded to `egress`:

| Object | Contents |
| --- | --- |
| `summary.json` | Software versions, GPU, timing and the main COCO metrics |
| `bbox.json` | Every box detection, in COCO results format |
| `segm.json` | Every mask detection, in COCO results format |

Submit it with the default of all 5,000 images:

```console
curl -k -u "$FRIDGE_AUTH" -X POST \
  -H "Content-Type: application/json" \
  -d '{"namespace": "argo-workflows", "template_name": "coco-evaluate", "parameters": []}' \
  "$FRIDGE_URL/workflowevents/from_template/"
```

To try the template quickly first, set `num-images` to a small number such as `100`.
The metrics are then only for those images, so they will not match the published figures.

The log reports progress every 50 images, then COCO's standard evaluation tables.

### Checking the results

Download the summary:

```console
curl -k -u "$FRIDGE_AUTH" -OJ \
  "$FRIDGE_URL/object/egress/experiments/coco/coco-evaluate-abcde/summary.json"
```

```json
{
  "model": "maskrcnn_resnet50_fpn_v2",
  "dataset": "COCO val2017",
  "images_evaluated": 5000,
  ...
  "metrics": {
    "bbox": {"mAP": 0.47, "AP50": ..., ...},
    "segm": {"mAP": 0.42, "AP50": ..., ...}
  }
}
```

Over all 5,000 images, the box `mAP` should be close to 0.474 and the mask `mAP` close to 0.418, the figures [published by Torchvision](https://pytorch.org/vision/stable/models/generated/torchvision.models.detection.maskrcnn_resnet50_fpn_v2.html) for these weights.
Matching them shows that the data, the weights, the software and the GPU are all working correctly together.

`bbox.json` and `segm.json` are large, as they hold every detection.
Download them only if you need them.

## Cleaning up

The inputs stay in `ingress` until they are deleted.
Delete them when you have finished, for example:

```console
curl -k -u "$FRIDGE_AUTH" -X DELETE "$FRIDGE_URL/object/ingress/val2017.zip"
```

With the generic S3 identity, Job Submitters cannot delete from `egress`.
Ask your TRE Administrators to remove old results if needed.

(use-tutorial-coco-adapting)=
## Adapting the templates

To run on a cluster with Intel GPUs, such as Dawn, change in `coco_smoke_test.yaml` and `coco_evaluate.yaml`:

- the GPU resource from `amd.com/gpu` to `gpu.intel.com/i915`
- the supplemental group from `992` to `110`
- the image to a PyTorch build for Intel GPUs, and the scripts' `torch.cuda` calls and `cuda:0` device to their `torch.xpu` and `xpu:0` equivalents

See [Resources](#workflow-resources) for the GPU settings of each cluster.

Each stage unpacks the dataset again from the archives, which is simple but repeats work.
For datasets that are much larger, or used by many jobs, consider unpacking them once onto the shared volume and mounting `block-storage-pvc` in the templates instead, as described in [Data](../deploy/workflow_templates.md).
