#!/usr/bin/env bash
# Private userspace runtime; keep JetPack's installed driver and CUDA toolkit.
set -euo pipefail
runtime="$HOME/opt/pipestudio-arm"
export PATH="/usr/local/cuda/bin:$PATH"
export BLENDER_SYSTEM_RESOURCES="$runtime/bin/5.1"
exec "$runtime/syslib/ld-linux-aarch64.so.1" \
    --library-path "$HOME/opt/oidn-pipestudio/lib:$runtime/libExt:$runtime/syslib:/usr/lib/aarch64-linux-gnu/nvidia:/usr/lib/aarch64-linux-gnu/tegra" \
    "$runtime/bin/blender" "$@"
