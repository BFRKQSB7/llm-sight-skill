#!/usr/bin/env bash
# 打包 llm-sight 三个版本：
#   _lite     = git 跟踪文件（无内置模型，setup 首次联网下载）
#   _standard = _lite + v6 small 模型（CPU 默认，开箱即用）
#   _full     = _standard + v6 medium 模型 + gpu_module.marker（GPU 默认 + 默认装 DirectML）
# 用法: bash scripts/package.sh <运行时skill目录(含 models/rapidocr/)> [输出目录，默认 dist]
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

CLS="ch_ppocr_mobile_v2.0_cls_mobile.onnx"
SMALL_DET="PP-OCRv6_det_small.onnx"; SMALL_REC="PP-OCRv6_rec_small.onnx"
MEDIUM_DET="PP-OCRv6_det_medium.onnx"; MEDIUM_REC="PP-OCRv6_rec_medium.onnx"
CYRILLIC_REC="cyrillic_PP-OCRv5_rec_mobile.onnx"  # standard 附带的俄文 rec（已验证可用）
RAPID="$MODELS_SRC/models/rapidocr"

copy_models() {
  mkdir -p "$STAGE/models/rapidocr"
  for f in "$@"; do
    if [ ! -f "$RAPID/$f" ]; then
      echo "WARN: 缺模型文件 $f，跳过"
      continue
    fi
    cp "$RAPID/$f" "$STAGE/models/rapidocr/"
  done
}

build_zip "$STAGE" "$DIST/llm-sight-${VERSION}_lite.zip"

if [ -n "$MODELS_SRC" ] && [ -d "$RAPID" ]; then
  # _standard: v6 small（CPU 默认）+ 俄文 rec（已验证可用）；korean/arabic 按需下载
  copy_models "$CLS" "$SMALL_DET" "$SMALL_REC" "$CYRILLIC_REC"
  build_zip "$STAGE" "$DIST/llm-sight-${VERSION}_standard.zip"
  # _full: 再加 v6 medium（GPU 默认模型）+ marker
  copy_models "$MEDIUM_DET" "$MEDIUM_REC"
  touch "$STAGE/gpu_module.marker"
  build_zip "$STAGE" "$DIST/llm-sight-${VERSION}_full.zip"
else
  echo "WARN: 未提供 models/rapidocr 目录，standard/full 跳过"
fi

rm -rf "$STAGE_ROOT"
ls -la "$DIST" | grep llm-sight
