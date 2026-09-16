#!/usr/bin/env bash
set -e
export LD_LIBRARY_PATH="$HOME/opt/blender-pipestudio/cmake-make/libExt${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="/usr/local/cuda/bin:$PATH"
exec "$HOME/opt/blender-pipestudio/cmake-make/bin/blender" "$@"
