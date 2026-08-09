#!/usr/bin/env bash
# 打包 llm-sight 两个版本：
#   v1 = git 跟踪文件（无内置模型）
#   v2 = v1 + models/（内置 OCR 模型，唯一区别）
# 用法: bash scripts/package.sh <运行时skill目录(含 models/)> [输出目录，默认 dist]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION="$(cat "$REPO_ROOT/VERSION")"
MODELS_SRC="${1:-}"
DIST="${2:-$REPO_ROOT/dist}"

STAGE_ROOT="$(mktemp -d)"
STAGE="$STAGE_ROOT/llm-sight"
mkdir -p "$STAGE" "$DIST"

# 用 git 选文件（只含跟踪文件），再 python zipfile 打包（跨平台，无外部 zip 依赖）
git archive --format=tar HEAD | tar -x -C "$STAGE"

build_zip() {
  local root="$1" out="$2"
  python - "$root" "$out" <<'PY'
import sys, zipfile, os
root, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            z.write(p, os.path.join("llm-sight", os.path.relpath(p, root)))
print("wrote", out)
PY
}

build_zip "$STAGE" "$DIST/llm-sight-v1-$VERSION.zip"

if [ -n "$MODELS_SRC" ] && [ -d "$MODELS_SRC/models/official_models" ]; then
  mkdir -p "$STAGE/models"
  cp -r "$MODELS_SRC/models/official_models" "$STAGE/models/"
  build_zip "$STAGE" "$DIST/llm-sight-v2-$VERSION.zip"
else
  echo "WARN: 未提供 models 目录（或 models/official_models 缺失），v2 跳过"
fi

rm -rf "$STAGE_ROOT"
ls -la "$DIST" | grep llm-sight
