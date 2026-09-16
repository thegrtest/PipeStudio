#!/usr/bin/env bash
# Compile the bundled Cycles source for Orin with its installed CUDA toolkit.
# Only private Pipe Studio runtime/cache files are written.
set -euo pipefail
cycles="$HOME/opt/pipestudio-arm/bin/5.1/scripts/addons_core/cycles"
cache="$HOME/.cache/pipestudio"
test -f "$cycles/source/kernel/device/cuda/kernel.cu"
mkdir -p "$cache"
/usr/local/cuda/bin/nvcc -arch=sm_87 --cubin \
    "$cycles/source/kernel/device/cuda/kernel.cu" \
    -o "$cache/kernel_sm_87.cubin" -m64 --use_fast_math -DNVCC \
    -DWITH_NANOVDB -I"$cycles/source" > "$cache/kernel-build.log" 2>&1
zstd -q -f "$cache/kernel_sm_87.cubin" -o "$cycles/lib/kernel_sm_87.cubin.zst"
sha256sum "$cycles/lib/kernel_sm_87.cubin.zst" > "$cache/kernel-sm87.sha256"
/usr/local/cuda/bin/nvcc --version > "$cache/kernel-compiler.txt"
cat "$cache/kernel-sm87.sha256"
