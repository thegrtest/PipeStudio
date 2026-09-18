# Three-device generation

## Assembled brass/copper inspection track

The assembly scene has a separate launcher so its defect and part-tracking
classes cannot be mixed with the older tapered-pipe dataset. To generate the
latest camera-matched assembly finish on the two remote GPUs while leaving the
desktop idle:

```powershell
.\.venv\Scripts\python.exe remote/assembly_fleet.py launch --nodes spark,agx --count 5000
.\.venv\Scripts\python.exe remote/assembly_fleet.py status
.\.venv\Scripts\python.exe remote/assembly_fleet.py stop
.\.venv\Scripts\python.exe remote/assembly_fleet.py resume
.\.venv\Scripts\python.exe remote/assembly_fleet.py fetch
```

Count is per selected device. New runs use independent specimen ranges, native
1920 × 1200 images and 96 samples. The dent/fold plan retains nominal 45% dents,
45% folds and 10% good controls (partial final blocks can differ slightly).
Lighting is selected independently of condition: approximately 70% Balanced,
15% Current and 15% Four Lines, with the existing small exposure, light-balance,
surface-finish, softness and sensor-noise variations. Each specimen keeps its
finish and light preset through its three rolling views.

The existing node lock, immutable source deployment and dashboard are reused.
Assembly rendering runs in bounded chunks, verifies committed outputs, retries
up to three attempts without progress, checks free disk space and pauses between
images. Completed jobs receive mask/box and split validation. Outputs remain in
each node's job folder under `all/images`, `all/labels` and separate
`tracking/all/images`, `tracking/all/labels`; fetch retrieves these per-device
folders with transfer hash checks. The ordinary domain collector deliberately
does not merge assembly outputs into its different class mapping.

The saved assembly run is recorded in `.cache/assembly-fleet-active.json`.
Use `--run` to operate on a particular saved assembly job. Devices must be idle
before launch; earlier jobs remain independently resumable. The desktop is not
selected unless explicitly included in `--nodes`.

## Older tapered-pipe inspection environments

The default is the **new camera-matched tapered pipes**. One saved global plan is
partitioned into unique specimens across the desktop, DGX Spark and AGX. Each run
ships a checksummed copy of the renderer code and assets. Editing the workspace
after a run starts does not change that run or prevent resuming it.

All three devices have GPU runtimes and dedicated SSH access configured. Use the
readiness workflow below to verify the current environment, including images,
labels and masks, before starting production.

## Update and launch

Double-click **Update and Ready Fleet.cmd** after making environment changes.
It compares file hashes, sends only changed files to each device, and reuses the
files already present there. New code is assembled in a separate directory and
activated only after every file is verified. Older batches keep their original
code and can still resume. No Git commit, push, runtime download or password entry
is needed for ordinary environment updates.

The command then generates full-quality test images on each device: fold, dent,
soap stain and oil stain, plus a clean specimen when good images are enabled.
It checks the labels, masks and transfer
hashes and collects a combined test gallery on the desktop. A successful check is
cached for that exact renderer version, runtime configuration and quality. Running
the command again without changes skips both file transfers and render tests.
Use `-Force` with the Ready action after manually changing a driver or installed
runtime to request fresh render checks.

Finally, it stages a balanced 3,200-image production plan on all three devices,
without starting production. **Start Fleet Generation.cmd** repeats the cheap
update/readiness check, retests changed environments if needed, and then starts
the prepared production cycle. Active generation prevents updates to that device;
stop or finish the current batch first. The dashboard remains read-only.
New plans get a fresh random seed by default. Pass `-Seed` when deliberately
reproducing a previous dataset; saved runs always retain their original seed.

For an active cycle, `.venv\Scripts\python.exe remote/roll_fleet_update.py --pause desktop`
stages the latest project while remote devices render, then switches devices one
at a time after the current image finishes. The desktop stays paused. The new
job keeps completed images and the 3,000-image targets; remaining specimens use
the latest YOLOX profile with defects only. Source segments in each manifest
record which renderer produced the older images. This updates project files;
the installed Blender and CUDA runtimes stay pinned.

The last readiness receipt is `.cache/fleet-ready.json`. Its `production_run`
points to the saved plan and its `test_dataset` points to the checked examples.

## Dashboard

Double-click **Fleet Dashboard.cmd** in the project root. It opens a local page
with the latest job's completed/planned images and worker state for each device.
The combined count is the sum of those latest jobs, not an all-time dataset total.
It refreshes every 15 seconds, using tiny progress records instead of scanning
image directories. Each card also shows its last completed image; click it to
enlarge. A new image is resized to at most 960 by 720 pixels and JPEG-compressed
on its device before transfer. Unchanged previews are reused, and only two
versions per device are cached in memory. Original training images and render
workers are untouched. A disconnected device keeps its last known count and
preview, marked unavailable. Pending devices have no invented count.

The server binds only to `127.0.0.1`, uses Python's standard library plus the
existing Pillow install for thumbnails, and has no paid service, web framework,
database or video streaming. Polling continues while
the local server is running, even after the browser tab closes. To stop only
monitoring, run `powershell -File remote/Stop-FleetDashboard.ps1`.

The dashboard monitors fleet jobs. Separately launched Blender or legacy rolling
capture jobs are outside these counts. Closing it does not stop render workers.

## Commands from the project directory

```powershell
# Connectivity/readiness only; no renders.
powershell -File remote/Fleet.ps1 -Action Doctor

# Transfer changes without rendering or preparing a production cycle.
powershell -File remote/Fleet.ps1 -Action Sync

# Update, test new versions, and stage a production plan; no production renders.
powershell -File remote/Fleet.ps1 -Action Ready -Count 3200 -Quality full

# Explicitly start production, updating and checking new versions automatically.
powershell -File remote/Fleet.ps1 -Action Launch -Count 3200 -Quality full

# Generate exactly 3,000 on EACH device (9,000 total), with independent seeds
# and equal camera coverage per device. Without -PerNode, Count is fleet-wide.
powershell -File remote/Fleet.ps1 -Action Launch -Count 3000 -PerNode -Quality full

# Pause at image boundaries, replace remaining good specimens with labeled
# defects, preserve committed outputs/counts, and resume all three devices.
# Also saves defects-only as the default for future fleet production.
powershell -File remote/Fleet.ps1 -Action Defects-Only

# Save a full-quality production plan without starting it.
powershell -File remote/Fleet.ps1 -Action Prepare -Count 3200 -Quality full

# When production is authorized, deploy and start that exact prepared run.
powershell -File remote/Fleet.ps1 -Action Start -Run "<folder returned by Prepare>"

powershell -File remote/Fleet.ps1 -Action Status
powershell -File remote/Fleet.ps1 -Action Stop
powershell -File remote/Fleet.ps1 -Action Resume
powershell -File remote/Fleet.ps1 -Action Fetch
```

`Stop` finishes the current image before stopping. `Resume` verifies committed
files and uses the saved code/plan, without regenerating completed specimens.

`Defects-Only` creates a continuation job with the same target count, specimen
IDs, full-quality renderer and existing outputs. It verifies and carries completed
images, labels and masks into that job, leaving the previous job intact. Previously
completed good images are retained; every remaining specimen contains one or two
labeled defects. The preference is saved in `fleet_nodes.local.json` under
`defaults.defects_only`. The Python CLI accepts `--no-defects-only` to explicitly
include good specimens in a later new production plan.
`Fetch` requires each worker to be finished or paused, verifies transferred files,
and collects a single `exports/fleet_runs/<run>/dataset/all/` with `images/`,
`labels/`, `masks/`, `metadata/`, `classes.txt`, `data.yaml` and a manifest.
The parent folder includes validation results, a contact sheet and a gallery.
This is synthetic training data; use an independent real validation set.

For a bounded check: add `-Smoke -Quality quick` to `Start`. It generates three
images per selected node (clean, fold and dent). To explicitly test a subset,
add `-Nodes desktop,spark`. This does not certify an excluded node.

Production counts are multiples of 40 because the domain plan balances eight
setups, clean specimens, four defect classes and multi-defect cases. Full quality
uses the domain plan's full resolution and sample settings on every node; node
weights change work allocation, not image quality. Initial weights are 8:4:1 for
desktop:Spark:AGX, based on the full-quality five-case check (approximately 19,
41 and 158 seconds of rendering respectively). These are throughput estimates,
not fixed guarantees; scene complexity affects timings.

## Node configuration and runtime

`fleet_nodes.local.json` is intentionally ignored by Git. Copy
`remote/fleet_nodes.example.json` and fill in each machine's Python, Blender and
project paths. It contains no passwords. SSH hosts require a verified host key and
an authorized identity; network setup and access authorization are separate from
the renderer. No listening worker service or root access is required.

The desktop uses installed Blender 5.1.2 / OptiX. Spark uses a tested Blender
5.1.0 ARM build / OptiX. Its source is the community-maintained
[CoconutMacaroon Blender ARM64 v10-5.1 release](https://github.com/CoconutMacaroon/blender-arm64/releases/tag/v10-5.1),
not an official Blender binary. Original archive SHA256:
`f8c41e767bfb8e42c0e3190ec5132c3bae413c568a17664388341c67d543ab1a`.

AGX uses CUDA with a locally compiled SM87 kernel for its installed CUDA 12.6
toolkit. Its OIDN 2.4.1 denoiser was rebuilt for baseline ARM64 instructions;
the bundled Spark CPU denoiser requires instructions absent on Orin. Rendering
stays on the GPU; denoising uses the compatible CPU OIDN build on both ARM nodes.
Image quality settings and the denoising algorithm remain the same.

The ARM runtimes use private libraries under each user's home; JetPack, the
system driver and system libc are not replaced. `build_agx_kernel.sh` and
`build_agx_denoiser.py` reproduce the AGX changes and record source/checksum
information. Runtime archives, credentials and output datasets are excluded from
renderer snapshots and Git. `{release}` in a Blender command resolves to the
saved snapshot, so launcher updates travel with the environment automatically.

Each node has an exclusive generation lock, bounded render retries, source and
output hash verification, and a 3 GB free-space guard. Render or validation
failures are surfaced in status and logs, with GPU fallback to CPU disabled.

## Temporary defect-class exclusions

`fleet_nodes.local.json` can set `defaults.allowed_defects` to `["FOLD", "DENT"]`.
Fleet preparation, smoke checks, launch, and rolling environment updates respect
this selection for both primary and secondary defects. Remove this setting or
list all four kinds to restore soap/oil generation. Class IDs remain unchanged.
`--allowed-defects FOLD DENT` overrides the configured selection for one command.

`remote/restrict_fleet_defects.py --request <saved-pause-request.json> --allowed FOLD DENT`
continues an existing plan using the same renderer and quality settings, preserving
every committed row and restarting only devices marked running in the request.
The request records the parent run and initial device states before pausing.

`remote/split_surface_dataset.py --source <collection> --soap <desktop-folder> --stain <desktop-folder>`
copies whole image/label pairs into separate archives and verifies hashes, PNGs,
and labels before removing those pairs from the original collection. Mixed images
retain all annotations; soap+oil images appear in both archives. Keep shared
images in the same training split when combining these datasets. The source
receipt excludes classes 2 and 3 from later incremental fleet collections. A
resumable journal preserves the original receipt and archive provenance.

## RGB render caching

The per-node environment option `PIPESTUDIO_RENDER_CACHE=beauty` enables Cycles
persistent data for RGB renders. Every label-mask pass uses a fresh render session.
`off` is the default and disables this optimization. Full caching is intentionally
not supported: the matched Spark trial found changed mask edges and one-pixel
YOLO box shifts when persistent data was also used for masks.

`verification/cache_benchmark.py` compares identical saved specimens, full native
resolution, 128 samples, glare retries, masks, boxes, and capture metadata. Trials
live outside production jobs and cannot enter normal fleet collection. Compare
RGB differences with an uncached repeat because GPU rendering can produce tiny
rounding differences even with unchanged settings.

`remote/enable_render_cache.py --trial spark=<comparison.json> --trial agx=<comparison.json> --production-trial <production-comparison.json>`
requires successful per-device comparisons before applying the policy. It changes
only `fast_pipeline.py` from the current immutable release, retains every planned
specimen and completed output, preserves paused devices, and saves cache policy
in continuation provenance and future node configuration. Updating the active
job requires this handoff; editing a running worker's configuration will not apply
the option safely.
