#!/usr/bin/env python3
"""llm-sight 环境引导器：check / install / config / update。

用系统 python 跑（纯 stdlib，零依赖）。skill 的 .venv 是依赖载体，由本脚本构建。
所有 OCR 工作文件（venv/models/config/tmp）都在 skill 目录内。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PY = VENV_DIR / "Scripts" / "python.exe" if os.name == "nt" else VENV_DIR / "bin" / "python"
CONFIG = SKILL_DIR / "config.json"
MODELS_JSON = Path(__file__).resolve().parent / "models.json"
COMMANDS_SRC = Path(__file__).resolve().parent.parent / "commands"
COMMANDS_DST = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~")) / ".claude" / "commands"

PY_DOWNLOAD_URL = "https://www.python.org/downloads/"
PY_MIN, PY_MAX = (3, 8), (3, 14)  # paddle has no wheels for 3.14+

DEFAULT_CONFIG = {
    "model": "PP-OCRv6_medium",
    "auto_update": True,
    "proxy": None,
    "manifest_url": None,
    "last_check": None,
    "installed_version": None,
}


def eprint(msg):
    print(msg, file=sys.stderr)


def load_models_map():
    return json.loads(MODELS_JSON.read_text(encoding="utf-8"))


def read_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            eprint(f"[config] 读取 config.json 失败（用默认）: {e}")
    return cfg


def write_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    eprint(f"[config] 已写入 {CONFIG}")


def run(cmd, **kw):
    eprint("[run] " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, **kw)


def find_python():
    """Return a usable system python, or None. Order: skill venv first, then system."""
    cands = [VENV_PY, None, None, None]
    py = shutil.which("py")
    pyth = shutil.which("python")
    pyth3 = shutil.which("python3")
    if py:
        cands[1] = [py, "-3.12"] if os.name == "nt" else [py]
    if pyth:
        cands[2] = [pyth]
    if pyth3:
        cands[3] = [pyth3]

    for cand in cands:
        if cand is None:
            continue
        if isinstance(cand, Path):
            exe = cand
            if not exe.exists():
                continue
            base = [str(exe)]
        else:
            exe = None
            base = list(cand)
        try:
            r = subprocess.run(base + ["-c", "import sys;print(sys.version_info[0],sys.version_info[1])"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                continue
            major, minor = map(int, r.stdout.strip().split())
            if (major, minor) >= PY_MIN and (major, minor) < PY_MAX:
                return (base, f"{major}.{minor}")
        except (subprocess.SubprocessError, ValueError):
            continue
    return None


def venv_ok():
    if not VENV_PY.exists():
        return False
    try:
        r = subprocess.run([str(VENV_PY), "-c", "import paddleocr;print(paddleocr.__version__)"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except subprocess.SubprocessError:
        return False


def ensure_venv(system_python):
    if venv_ok():
        eprint("[install] venv 已就绪，跳过构建")
        return
    eprint("[install] 创建 venv（首次，需几分钟）")
    run([system_python, "-m", "venv", str(VENV_DIR)], check=True)
    run([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    eprint("[install] 安装 paddlepaddle + paddleocr（约 1GB，请耐心等待）")
    run([str(VENV_PY), "-m", "pip", "install", "paddlepaddle", "paddleocr"], check=True)
    if not venv_ok():
        raise SystemExit("[install] venv 构建后 paddleocr 仍不可用")


def ensure_models(config, force=False):
    mmap = load_models_map()
    name = config.get("model") or DEFAULT_CONFIG["model"]
    if name not in mmap:
        raise SystemExit(f"[install] 未知模型: {name}（可用: {', '.join(mmap)}）")
    if not force and (SKILL_DIR / "models" / "official_models").exists():
        eprint("[install] 模型已存在，跳过下载")
        return
    if not VENV_PY.exists():
        raise SystemExit("[install] 缺 venv，请先跑 install 完成 venv 构建")
    params = mmap[name]
    snippet = (
        "import json,sys,os\n"
        "os.environ['PADDLE_PDX_CACHE_HOME']=sys.argv[2]\n"
        "from paddleocr import PaddleOCR\n"
        "cfg=json.load(open(sys.argv[1],encoding='utf-8'))\n"
        "PaddleOCR(use_doc_orientation_classify=False,use_doc_unwarping=False,"
        "use_textline_orientation=False,device='cpu',**cfg)\n"
        "print('MODELS_OK')\n"
    )
    tmp = SKILL_DIR / "tmp"
    tmp.mkdir(exist_ok=True)
    job = tmp / "warmup.json"
    job.write_text(json.dumps({k: v for k, v in params.items() if k != "desc"}, ensure_ascii=False), encoding="utf-8")
    eprint(f"[install] 下载模型 {name}（首次可能几分钟）")
    r = subprocess.run([str(VENV_PY), "-c", snippet, str(job), str(SKILL_DIR / "models")],
                       capture_output=True, text=True)
    job.unlink(missing_ok=True)
    if r.returncode != 0 or "MODELS_OK" not in r.stdout:
        raise SystemExit(f"[install] 模型下载失败:\n{r.stdout}\n{r.stderr}")
    config["installed_version"] = name
    write_config(config)


def install_commands():
    if not COMMANDS_SRC.is_dir():
        eprint("[install] 无 commands/ 目录，跳过")
        return
    COMMANDS_DST.mkdir(parents=True, exist_ok=True)
    for f in COMMANDS_SRC.glob("llm-sight-*.md"):
        shutil.copy2(f, COMMANDS_DST / f.name)
        eprint(f"[install] 斜杠命令已装: ~/.claude/commands/{f.name}")


def update_check(config):
    url = config.get("manifest_url")
    if not url:
        print("[update] manifest_url 未配置，跳过更新检查（可用 setup.py config --manifest-url <URL> 配置）")
        return 0
    try:
        opener = urllib.request.build_opener()
        proxy = config.get("proxy")
        if proxy:
            opener.add_handler(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        with opener.open(url, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[update] 检查失败（不影响使用）: {e}")
        return 0
    latest = data.get("latest")
    installed = config.get("installed_version") or config.get("model")
    if latest and installed and latest != installed:
        print(f"[update] 检测到新版本: {installed} -> {latest}（setup.py config --model {latest} 可切换）")
    elif latest and not installed:
        print(f"[update] 推荐模型: {latest}")
    else:
        print(f"[update] 已是最新（{installed}）")
    config["last_check"] = time.time()
    write_config(config)
    return 0


def cmd_check():
    print("[status] llm-sight 环境检查")
    print(f"[status] skill 目录: {SKILL_DIR}")
    found = find_python()
    if found:
        print(f"[status] python: {found[1]}")
    else:
        print(f"[status] python: 未找到（请安装 Python 3.8-3.13: {PY_DOWNLOAD_URL}）")
    print(f"[status] venv: {'ok' if venv_ok() else '缺失/不可用'}")
    models_ok = (SKILL_DIR / "models" / "official_models").exists()
    print(f"[status] models: {'ok' if models_ok else '缺失'}")
    cfg = read_config()
    print(f"[status] config: model={cfg.get('model')} auto_update={cfg.get('auto_update')} "
          f"proxy={cfg.get('proxy') or '无'} manifest_url={cfg.get('manifest_url') or '未配置'}")
    return 0


def cmd_install():
    found = find_python()
    if not found:
        print(f"[install] 未检测到可用的 Python（3.8-3.13）。请先安装: {PY_DOWNLOAD_URL}")
        return 2
    system_python, ver = found
    eprint(f"[install] 使用系统 python {ver}")
    ensure_venv(system_python)
    cfg = read_config()
    ensure_models(cfg)
    install_commands()
    print("[install] 完成。可用 /llm-sight-status 查看状态")
    return 0


def cmd_config(args):
    cfg = read_config()
    mmap = load_models_map()
    if args.model:
        if args.model not in mmap:
            print(f"[config] 未知模型 {args.model}。可用: {', '.join(mmap)}")
            return 1
        cfg["model"] = args.model
    if args.auto_update is not None:
        cfg["auto_update"] = args.auto_update
    if args.proxy is not None:
        cfg["proxy"] = args.proxy or None
    if args.manifest_url is not None:
        cfg["manifest_url"] = args.manifest_url or None
    write_config(cfg)
    print(f"[config] model={cfg['model']} auto_update={cfg['auto_update']} "
          f"proxy={cfg.get('proxy') or '无'} manifest_url={cfg.get('manifest_url') or '未配置'}")
    return 0


def cmd_update():
    cfg = read_config()
    return update_check(cfg)


def main():
    ap = argparse.ArgumentParser(description="llm-sight 环境引导器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="完整性检查")
    sub.add_parser("install", help="引导：建 venv、确保模型、装斜杠命令")
    p = sub.add_parser("config", help="查看/修改配置")
    p.add_argument("--model")
    p.add_argument("--auto-update", type=lambda s: s.lower() in ("1", "true", "on", "yes"))
    p.add_argument("--proxy", help="代理地址，如 http://127.0.0.1:<端口>（空串清除）")
    p.add_argument("--manifest-url", help="更新清单 URL（空串清除）")
    sub.add_parser("update", help="检查模型更新（手动触发）")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "install":
        return cmd_install()
    if args.cmd == "config":
        return cmd_config(args)
    if args.cmd == "update":
        return cmd_update()
    return 0


if __name__ == "__main__":
    sys.exit(main())
