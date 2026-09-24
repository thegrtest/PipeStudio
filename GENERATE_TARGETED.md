# Run the targeted generator on another machine

The `eval-gap` profile targets UPRIGHT, FOREGROUND and INVERTED inspection
cameras at native 640 × 640. A 3,000-image batch contains 1,000 frames per view,
1,350 Fold-primary frames, 1,350 Dent-primary frames and 300 clean controls.
Forty percent of frames contain two or three defects. All production frames
belong to training; keep real validation data separate.

The recipe includes small round dents, broad shallow dents, thin neck folds,
body buckles and neck crescents. Lighting, finish, slight blur, sensor noise
and background variation are independent of defect class. Each geometric
label must pass a comparison against the same scene with that defect removed,
as well as the glare check. Bounded retries retain the class and specimen;
an unresolved failure stops generation instead of publishing an invisible label.
These checks do not establish improved real-image detector accuracy.

## Install

Install Git LFS, Python 3.12 and a Blender 5.1 build compatible with the machine's
GPU. On Windows, start in a directory where you want the project:

```powershell
git lfs install
git clone https://github.com/thegrtest/PipeStudio.git
cd PipeStudio
git lfs pull
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For an existing checkout, use `git pull --ff-only` and `git lfs pull` after
preserving any local edits. On Linux, use `python3.12 -m venv .venv` and
`.venv/bin/python` in place of `.\.venv\Scripts\python.exe` below.

Blender is found on PATH or in the usual Windows install directory. If needed,
set `PIPE_STUDIO_BLENDER` to its executable path, or create the ignored
`local_runtime.json` with a `blender` field. Install Pillow/NumPy into the project
environment; Blender supplies its own `bpy`. For DGX/AGX ARM runtime setup, see
[fleet runtime notes](remote/FLEET.md#node-configuration-and-runtime).

## Preview, then start on this machine

These commands render on the machine where you execute them. They do not
require SSH or `fleet_nodes.local.json`.

```powershell
# 18 full-quality development examples, including per-defect comparison renders.
.\.venv\Scripts\python.exe generate_domain_dataset.py --profile eval-gap --preview --seed 925010000 --output exports/eval-gap-preview --chunk 2

# 3,000 production images with a separate specimen seed range.
.\.venv\Scripts\python.exe generate_domain_dataset.py --profile eval-gap --count 3000 --seed 925000000 --quality full --output exports/eval-gap-production --chunk 2
```

Use a fresh output directory and a non-overlapping seed range for each additional
batch or machine. The example production range is 925000000–925002999; it is
separate from the September 24 fleet batch. Production counts must be multiples
of 60. Preview always contains 18 full-quality examples, regardless of `--count`.
Add `--prepare-only` to write and validate a plan without rendering.

The output contains `all/images`, matching `all/labels`, masks, metadata,
`all/data.yaml`, the saved plan and progress records. IDs remain 0 Fold, 1 Dent,
2 Soap stain, 3 Oil stain; this supplement generates only Fold/Dent and clean
controls. Keep the intentional empty labels for clean controls. Do not merge
the development preview into real validation.

To pause, create an empty `cancel.flag` inside the output directory (Windows
also gets a **Stop After Current Image.cmd** shortcut). Resume with the same
renderer files:

```powershell
.\.venv\Scripts\python.exe generate_domain_dataset.py --output exports/eval-gap-production --resume --chunk 2
```

## Existing configured fleet

For devices that have already passed GPU runtime setup, use the Python fleet
CLI; the PowerShell wrapper does not expose the new profile option:

```powershell
.\.venv\Scripts\python.exe remote/fleet.py ready --nodes spark,agx --profile eval-gap --count 3000 --quality full --no-defects-only --allowed-defects FOLD DENT
# Inspect the test_dataset returned above, then use the returned production_run:
.\.venv\Scripts\python.exe remote/fleet.py start --nodes spark,agx --run "<production_run>"
.\.venv\Scripts\python.exe remote/fleet.py status --nodes spark,agx --run "<production_run>"
```

Fleet readiness uses a separate preview seed range and immutable renderer
snapshots. Git updates do not replace a running fleet job. Node paths, SSH
identities, installed runtimes, datasets and generated review pages are local
and are not distributed through GitHub.
