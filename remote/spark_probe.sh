#!/usr/bin/env bash
# Read-only inventory. No package installation, container startup or rendering.
set -u
printf '\nHost and operating system\n'
hostname
id -un
uname -m
cat /etc/os-release
printf '\nMemory and project disk\n'
free -h
df -h "$HOME"
printf '\nNVIDIA GPU\n'
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu --format=csv
else
    printf 'nvidia-smi unavailable\n'
fi
printf '\nInstalled command paths\n'
for tool in blender python3 git git-lfs docker nvcc tmux ffmpeg; do
    command -v "$tool" || true
done
printf '\nBlender version, if installed\n'
if command -v blender >/dev/null 2>&1; then blender --version | head -n 3; fi
printf '\nCUDA compiler, if installed\n'
if command -v nvcc >/dev/null 2>&1; then nvcc --version | tail -n 4; fi
printf '\nExisting GPU jobs\n'
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv || true
fi
printf '\nExisting Blender installations under standard local locations\n'
find "$HOME" /opt /usr/local -maxdepth 4 -type f -name blender -executable 2>/dev/null | head -n 20
