#!/usr/bin/env python3
"""Extract text from an image using PaddleOCR.

Designed for non-multimodal LLMs: one command in, plain text out.

Usage:
    python ocr.py <image_path_or_url> [more images...] [options]

Options:
    --lang <code>     OCR language. Default: ch (covers Chinese + Latin scripts
                      via the PP-OCRv6 50-language model). Common: en, japan,
                      korean, chinese_cht, french, german, ru, arabic.
    --format <fmt>    text | json. Default: text (one recognized line per line).
    --device <dev>    auto | cpu | gpu[:n]. Default: auto (GPU if usable, else CPU).
    --engine <eng>    paddle | onnxruntime | transformers. Default: paddle.
    --scratch <dir>   Where to put downloaded URL images. Default: skill's tmp/.
    --quiet           Suppress progress/status messages to stderr.

Exit codes:
    0  success (text may be empty)
    2  paddleocr not installed
    3  image file/URL unreachable or unreadable
    4  OCR runtime error
"""
import argparse
import json
import os
import sys
import tempfile
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Keep ALL of PaddleOCR's working files inside the skill directory:
# model downloads/cache land in <skill>/models instead of ~/.paddlex.
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", os.path.join(SKILL_DIR, "models"))

# Force UTF-8 on stdout/stderr. On Windows, redirected output otherwise uses
# the ANSI codepage (e.g. cp936), which mangles Chinese text for any consumer
# (the LLM) that reads this script's stdout.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Quiet the noisy Paddle/PaddleOCR INFO logs so stdout stays clean.
import logging
for name in ("paddle", "ppocr", "paddlex", "deploy", "profiler"):
    logging.getLogger(name).setLevel(logging.WARNING)


def eprint(msg):
    print(msg, file=sys.stderr)


def load_config():
    """Read user config (model choice, auto_update). Defaults if absent."""
    cfg = {"model": "PP-OCRv6_medium", "auto_update": True}
    try:
        with open(os.path.join(SKILL_DIR, "config.json"), encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def model_params(name):
    """Resolve a model name to PaddleOCR() kwargs via models.json."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json"), encoding="utf-8") as f:
            entry = json.load(f).get(name) or {}
        return {k: v for k, v in entry.items() if k != "desc" and v is not None}
    except (OSError, json.JSONDecodeError):
        return {}


def model_cached(name):
    """模型 det/rec 是否已下载到 skill/models/official_models。"""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json"), encoding="utf-8") as f:
            params = json.load(f).get(name) or {}
    except (OSError, json.JSONDecodeError):
        return True
    det = params.get("text_detection_model_name") or f"{name}_det"
    rec = params.get("text_recognition_model_name") or f"{name}_rec"
    base = os.path.join(SKILL_DIR, "models", "official_models")
    return os.path.isdir(os.path.join(base, det)) and os.path.isdir(os.path.join(base, rec))


def _confirm(prompt):
    """询问用户；stdin 无数据（管道/EOF）返回空串，不崩。"""
    try:
        return input(prompt).strip().lower()
    except (EOFError, OSError):
        return ""


def resolve_image(path, scratch):
    """Return a local file path. Downloads URLs into scratch dir."""
    if path.startswith(("http://", "https://")):
        os.makedirs(scratch, exist_ok=True)
        fname = os.path.join(scratch, os.path.basename(path.split("?")[0]) or "remote.png")
        eprint(f"[ocr] downloading {path}")
        try:
            urllib.request.urlretrieve(path, fname)
        except Exception as exc:
            raise RuntimeError(f"failed to download URL: {exc}") from exc
        return fname
    if not os.path.isfile(path):
        raise RuntimeError(f"no such file: {path}")
    return path


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("images", nargs="+", help="image path(s) or URL(s)")
    ap.add_argument("--lang", default="ch")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--engine", default="paddle")
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.quiet:
        for name in ("paddle", "ppocr", "paddlex", "deploy", "profiler"):
            logging.getLogger(name).setLevel(logging.ERROR)

    skill_dir = SKILL_DIR
    scratch = args.scratch or os.path.join(skill_dir, "tmp")

    try:
        from paddleocr import PaddleOCR
        import paddle
    except ImportError:
        eprint(
            "[ocr] paddleocr 未安装。请先运行引导（一次）：\n"
            f'[ocr]   "{os.path.join(skill_dir, ".venv", "Scripts", "python.exe")}" scripts/setup.py install\n'
            "[ocr] 或在 Claude Code 里 /llm-sight-status 查看环境、/llm-sight-config 配置后重试。"
        )
        sys.exit(2)

    # Resolve device: auto = gpu when the build actually has usable CUDA.
    device = args.device
    if device == "auto":
        device = "cpu"
        try:
            if paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
                device = "gpu"
        except Exception:
            pass

    # Warm up the pipeline lazily? No: PaddleOCR() constructor downloads models
    # on first use. That can take a while; tell the operator on stderr.
    cfg = load_config()
    model_name = cfg.get("model", "PP-OCRv6_medium")
    mp = model_params(model_name)
    eprint(f"[ocr] device={device} engine={args.engine} lang={args.lang} model={model_name}")

    # 模型未下载时绝不静默下载：先经用户确认（PaddleOCR 构造会自动下载，必须拦截）
    if not model_cached(model_name):
        eprint(f"[ocr] 模型 {model_name} 未下载，下载需数百 MB，必须你确认。")
        ans = _confirm(f"[ocr] 现在下载 {model_name} 吗？（y/N）: ")
        if ans.startswith("y"):
            import subprocess
            r = subprocess.run(
                [sys.executable, os.path.join(skill_dir, "scripts", "setup.py"), "models", "add", model_name],
                capture_output=True, text=True, timeout=1800,
            )
            if r.stdout:
                print(r.stdout)
            if r.stderr:
                eprint(r.stderr)
            if r.returncode != 0 or not model_cached(model_name):
                sys.exit(4)
        else:
            eprint(f"[ocr] 取消下载。请用 /llm-sight-model 或 setup.py models add {model_name} 下载（会询问你）。")
            sys.exit(4)

    try:
        ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang=args.lang,
            device=device,
            engine=args.engine,
            # paddle 3.x CPU + oneDNN hits a PIR-executor bug
            # (ConvertPirAttribute2RuntimeAttribute on DoubleAttribute);
            # disabling MKLDNN routes around it. GPU is unaffected.
            enable_mkldnn=False,
            **mp,
        )
    except Exception as exc:
        eprint(f"[ocr] failed to initialize PaddleOCR: {exc}")
        if cfg.get("auto_update"):
            eprint("[ocr] 初始化失败，尝试自动检查模型更新...")
            try:
                import subprocess
                r = subprocess.run(
                    [sys.executable, os.path.join(skill_dir, "scripts", "setup.py"), "update"],
                    capture_output=True, text=True, timeout=120,
                )
                if r.stdout.strip():
                    eprint(r.stdout.strip())
            except Exception:
                pass
        else:
            eprint("[ocr] 可运行 /llm-sight-update 手动检查模型更新")
        sys.exit(4)

    results = []
    for img in args.images:
        try:
            local = resolve_image(img, scratch)
            eprint(f"[ocr] recognizing: {img}")
            ocr_results = ocr.predict(local)
        except Exception as exc:
            if not isinstance(exc, RuntimeError) and not args.images:
                raise
            eprint(f"[ocr] error on {img}: {exc}")
            results.append({"image": img, "error": str(exc)})
            continue

        for res in ocr_results:
            texts = list(res.get("rec_texts", []))
            scores = [float(s) for s in res.get("rec_scores", [])]
            boxes = [
                [[int(round(float(c))) for c in pt] for pt in poly]
                for poly in res.get("rec_polys", [])
            ]
            results.append(
                {"image": img, "texts": texts, "scores": scores, "boxes": boxes}
            )

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            if item.get("error"):
                print(f"# {item['image']}: ERROR {item['error']}")
                continue
            print(f"# {item['image']}")
            if not item["texts"]:
                print("(no text detected)")
            else:
                for t in item["texts"]:
                    if t.strip():
                        print(t)
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
