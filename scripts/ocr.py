#!/usr/bin/env python3
"""Extract text from an image using rapidocr (PP-OCRv6 ONNX + onnxruntime).

Designed for non-multimodal LLMs: one command in, plain text out.

Usage:
    python ocr.py <image_path_or_url> [more images...] [options]

Options:
    --lang <code>     ch (default, covers Chinese + English), en, chinese_cht,
                      japan. v6 模型仅支持这 4 种语言；其他语言（如 korean）需
                      切换 v4/v5 模型（/llm-sight-model）。
    --format <fmt>    text | json. Default: text (one recognized line per line).
    --device <dev>    auto | cpu | gpu. Default: auto (gpu if usable, else cpu).
    --scratch <dir>   Where to put downloaded URL images. Default: skill's tmp/.
    --quiet           Suppress progress/status messages to stderr.

Exit codes:
    0  success (text may be empty)
    2  rapidocr not installed
    3  image file/URL unreachable or unreadable
    4  OCR runtime error
"""
import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_ROOT = os.path.join(SKILL_DIR, "models", "rapidocr")
CLS_FILE = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"

# Force UTF-8 on stdout/stderr. On Windows, redirected output otherwise uses
# the ANSI codepage (e.g. cp936), which mangles Chinese text for any consumer
# (the LLM) that reads this script's stdout.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Quiet the noisy RapidOCR logs so stdout stays clean.
import logging
for name in ("rapidocr", "onnxruntime", "onnx"):
    logging.getLogger(name).setLevel(logging.WARNING)


def eprint(msg):
    print(msg, file=sys.stderr)


DEFAULT_CONFIG = {
    "model_cpu": "PP-OCRv6_small",
    "model_gpu": "PP-OCRv6_medium",
    "gpu": False,
    "gpu_capable": False,
    "auto_update": True,
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(os.path.join(SKILL_DIR, "config.json"), encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    # 兼容旧版单一 model 字段（迁移到 model_cpu / model_gpu）
    if "model" in cfg and cfg.get("model"):
        if not cfg.get("model_cpu"):
            cfg["model_cpu"] = cfg["model"]
        if not cfg.get("model_gpu"):
            cfg["model_gpu"] = cfg["model"]
        cfg.pop("model", None)
    return cfg


def write_config(cfg):
    try:
        with open(os.path.join(SKILL_DIR, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def model_params(name):
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json"),
                  encoding="utf-8") as f:
            return json.load(f).get(name) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def model_cached(name):
    mp = model_params(name)
    if not mp.get("det_file"):
        return True
    files = [mp.get("det_file"), mp.get("rec_file"), CLS_FILE]
    return all(f and os.path.isfile(os.path.join(MODEL_ROOT, f)) for f in files)


def gpu_hardware_capable():
    """符合要求的显卡判定：能创建硬件 D3D11 设备（现代显卡皆满足，隐含 DX12）。
    不依赖 onnxruntime-directml 包——模块删了也能判定硬件是否支持。"""
    if os.name != "nt":
        return False
    try:
        import ctypes
        d3d11 = ctypes.WinDLL("d3d11.dll")
        d3d11.D3D11CreateDevice.restype = ctypes.c_long
        device = ctypes.c_void_p()
        ctx = ctypes.c_void_p()
        fl = ctypes.c_uint(0xB000)  # D3D_FEATURE_LEVEL_11_0
        hr = d3d11.D3D11CreateDevice(
            None, 1, 0, 0, ctypes.byref(fl), 1, 7,
            ctypes.byref(device), None, ctypes.byref(ctx))
        return hr == 0
    except Exception:
        return False


def gpu_module_installed():
    try:
        importlib.metadata.distribution("onnxruntime-directml")
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def sync_gpu_capable(cfg):
    """每次运行检测硬件 D3D12 能力并同步 config 的 gpu_capable（首次调用落盘）。"""
    capable = gpu_hardware_capable()
    if cfg.get("gpu_capable") != capable:
        cfg["gpu_capable"] = capable
        write_config(cfg)
    if not capable and gpu_module_installed():
        eprint("[ocr] 检测到本机无法使用 GPU 加速，但已安装 GPU 模块（约占 150MB）。")
        eprint("[ocr] 建议删除模块释放空间；更换支持 DirectML 的设备后再重新下载：")
        eprint('[ocr]   /llm-sight-config --gpu-module remove')
    return capable


def _confirm(prompt):
    """询问用户；stdin 无数据（管道/EOF）返回空串，不崩。"""
    try:
        return input(prompt).strip().lower()
    except (EOFError, OSError):
        return ""


def _readline_raw(prompt):
    """读取一行原样输入（用于模型名选择）；EOF 返回空串。"""
    try:
        return input(prompt).strip()
    except (EOFError, OSError):
        return ""


def installed_models_info():
    """已装模型列表：[(name, size_mb), ...]。"""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json"),
                  encoding="utf-8") as f:
            mmap = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return [(n, m.get("size_mb")) for n, m in mmap.items()
            if m.get("det_file") and model_cached(n)]


def ask_other_model(refused_name):
    """问是否下载其他模型；返回选中的模型名，或 None（不下载）。"""
    if not sys.stdin.isatty():
        return None
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json"),
                  encoding="utf-8") as f:
            mmap = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    inst = installed_models_info()
    if inst:
        print("[ocr] 已安装的模型（体积）：" + "、".join(f"{n} ({s}MB)" for n, s in inst))
    cands = [n for n in mmap if n != refused_name]
    print("[ocr] 可选的其他模型（体积 · 识别率 · 支持语言 · 适合人群）：")
    for i, n in enumerate(cands, 1):
        m = mmap[n]
        print(f"  {i}. {n} — {m.get('size_mb')}MB · 识别率 det {m.get('det_hmean')}%/rec "
              f"{m.get('rec_acc')}% · 语言 {m.get('langs', '?')} · {m.get('who')}")
    s = _readline_raw("输入编号或名称选一个下载（回车=不下载，自动用已装的）: ")
    if not s:
        return None
    if s.isdigit() and 1 <= int(s) <= len(cands):
        return cands[int(s) - 1]
    if s in mmap:
        return s
    print("[ocr] 无效输入，视为不下载。")
    return None


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


def best_installed_model():
    """返回已装模型里识别率最高的一个（无则 None）。"""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json"),
                  encoding="utf-8") as f:
            mmap = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    installed = [n for n, m in mmap.items() if m.get("det_file") and model_cached(n)]
    if not installed:
        return None
    return max(installed, key=lambda n: model_params(n).get("rec_acc") or 0)


def download_model(model_name, cfg):
    """下载所选模型（经用户确认后调用 setup.py models add）。"""
    import subprocess as sp
    cmd = [sys.executable, os.path.join(SKILL_DIR, "scripts", "setup.py"), "models", "add", model_name]
    if cfg.get("proxy"):
        cmd += ["--proxy", cfg["proxy"]]
    r = sp.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.stdout:
        print(r.stdout)
    if r.stderr:
        eprint(r.stderr)
    return r.returncode == 0 and model_cached(model_name)


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("images", nargs="+", help="image path(s) or URL(s)")
    ap.add_argument("--lang", default="ch")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.quiet:
        for name in ("rapidocr", "onnxruntime", "onnx"):
            logging.getLogger(name).setLevel(logging.ERROR)

    scratch = args.scratch or os.path.join(SKILL_DIR, "tmp")

    try:
        from rapidocr import RapidOCR
        from rapidocr.utils.typings import LangRec, ModelType, OCRVersion
    except ImportError:
        eprint(
            "[ocr] rapidocr 未安装。请先运行引导（一次）：\n"
            f'[ocr]   "{os.path.join(SKILL_DIR, ".venv", "Scripts", "python.exe")}" scripts/setup.py install\n'
            "[ocr] 或在 Claude Code 里 /llm-sight-status 查看环境、/llm-sight-config 配置后重试。"
        )
        sys.exit(2)

    cfg = load_config()
    capable = sync_gpu_capable(cfg)  # 硬件是否支持 DirectX12
    module = gpu_module_installed()
    gpu_usable = capable and module

    # 解析活动设备
    use_gpu = cfg.get("gpu", False) and gpu_usable
    if args.device == "cpu":
        use_gpu = False
    elif args.device == "gpu":
        use_gpu = gpu_usable
        if not gpu_usable:
            eprint("[ocr] GPU 不可用（硬件不支持或未装 GPU 模块），回落 CPU。")
    if cfg.get("gpu", False) and not gpu_usable:
        eprint("[ocr] config 里启用了 GPU 但当前不可用（缺模块或硬件不支持），本次回落 CPU。")

    # 批量识别：GPU 模块已装且硬件支持但未启用 → 询问本次是否启用
    if not use_gpu and gpu_usable and len(args.images) > 1:
        ans = _confirm(
            f"[ocr] 批量识别 {len(args.images)} 张图。是否本次启用 GPU 加速（更快）？(y/N): "
        )
        if ans.startswith("y"):
            use_gpu = True

    # 模型按活动设备选（CPU/GPU 各自独立配置）
    model_name = cfg.get("model_gpu" if use_gpu else "model_cpu") or (
        DEFAULT_CONFIG["model_gpu"] if use_gpu else DEFAULT_CONFIG["model_cpu"]
    )
    mp = model_params(model_name)

    eprint(f"[ocr] device={'gpu' if use_gpu else 'cpu'} lang={args.lang} model={model_name}")

    # 默认模型未下载 → 询问下载默认 → 询问其他 → 否则自动指定（已装最佳 / 设默认后退出）
    if not model_cached(model_name):
        inst = installed_models_info()
        if inst:
            eprint("[ocr] 已安装的模型（体积）：" + "、".join(f"{n} ({s}MB)" for n, s in inst))
        ans = _confirm(
            f"[ocr] 默认模型 {model_name} 未下载（{mp.get('size_mb')}MB · 识别率 "
            f"det {mp.get('det_hmean')}%/rec {mp.get('rec_acc')}% · 语言 {mp.get('langs', '?')}）。"
            f"现在下载吗？（y=下载 / N=再看看）: "
        )
        if ans.startswith("y"):
            if not download_model(model_name, cfg):
                sys.exit(4)
        else:
            other = ask_other_model(model_name)
            if other:
                if not download_model(other, cfg):
                    sys.exit(4)
                model_name = other
                mp = model_params(other)
            else:
                fb = best_installed_model()
                if fb:
                    eprint(f"[ocr] 不下载，自动指定使用已安装的 {fb} 识别。")
                    eprint("[ocr]   想换模型可 /llm-sight-model。")
                    model_name = fb
                    mp = model_params(fb)
                else:
                    eprint(f"[ocr] 未安装任何模型，本次无法识别。已自动指定默认模型为 {model_name}。")
                    eprint(f"[ocr]   可稍后用 /llm-sight-model 或 setup.py models add {model_name} 下载。")
                    sys.exit(4)

    # 构建 rapidocr 参数（枚举值）
    try:
        params = {
            "Global.model_root_dir": MODEL_ROOT,
            "Det.ocr_version": OCRVersion(mp["ocr_version"]),
            "Det.model_type": ModelType(mp["model_type"]),
            "Rec.ocr_version": OCRVersion(mp["ocr_version"]),
            "Rec.model_type": ModelType(mp["model_type"]),
            "Rec.lang_type": LangRec(args.lang),
            "EngineConfig.onnxruntime.use_dml": use_gpu,
        }
    except (KeyError, ValueError) as exc:
        eprint(f"[ocr] 模型 {model_name} 或语言 {args.lang} 无效: {exc}")
        sys.exit(4)

    try:
        engine = RapidOCR(params=params)
    except Exception as exc:
        msg = str(exc)
        if "lang_type" in msg and mp.get("ocr_version", "").startswith("PP-OCRv6"):
            eprint(f"[ocr] {model_name}（v6）仅支持语言: ch / en / chinese_cht / japan。")
            eprint("[ocr] 其他语言（如 korean）需切换 v4/v5 模型：/llm-sight-model")
        eprint(f"[ocr] 初始化失败: {msg}")
        sys.exit(4)

    results = []
    for img in args.images:
        try:
            local = resolve_image(img, scratch)
            eprint(f"[ocr] recognizing: {img}")
            res = engine(local)
            texts = list(res.txts) if getattr(res, "txts", None) else []
            scores = [float(s) for s in (getattr(res, "scores", None) or ())]
            boxes = res.boxes.tolist() if getattr(res, "boxes", None) is not None else []
            results.append({"image": img, "texts": texts, "scores": scores, "boxes": boxes})
        except Exception as exc:
            eprint(f"[ocr] error on {img}: {exc}")
            results.append({"image": img, "error": str(exc)})
            continue

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
