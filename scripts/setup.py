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
    "help_hint": True,
    "proxy": None,
    "manifest_url": None,
    "last_check": None,
    "installed_version": None,
}


def eprint(msg):
    print(msg, file=sys.stderr)


def load_models_map():
    return json.loads(MODELS_JSON.read_text(encoding="utf-8"))


def _readline(prompt):
    """input() 的健壮版：stdin 是 TTY 但无数据（管道/EOF）时返回空串，不崩。"""
    try:
        return input(prompt)
    except (EOFError, OSError):
        return ""


def ask_model(mmap, default):
    """交互询问下载哪个模型；空输入/非交互返回 None（由调用方用默认）。"""
    if not sys.stdin.isatty():
        return None
    print("需要下载一个 OCR 模型才能识别图片文字（首次一次性，每个约 100-300MB）。")
    print("可选模型（默认 PP-OCRv6_medium，多数场景够用）：")
    for i, name in enumerate(mmap, 1):
        print(f"  {i}. {name} — {mmap[name].get('desc', '')}")
    while True:
        s = _readline(f"输入编号或名称选择（回车用默认 {default}）: ").strip()
        if not s:
            return default
        if s.isdigit() and 1 <= int(s) <= len(mmap):
            return list(mmap)[int(s) - 1]
        if s in mmap:
            return s
        print("无效，重试")


def ask_proxy():
    """交互询问代理地址；空回车=直连；非交互返回 None。"""
    if not sys.stdin.isatty():
        return None
    print("接下来要下载依赖（约 1GB）和 OCR 模型（数百 MB）。")
    print("如果网络访问下载源（PyPI / HuggingFace）需要代理，请填代理地址；")
    print("不需要则直接回车（直连下载）。代理地址会保存到本机 config，之后更新检查也用它。")
    s = _readline("代理地址，格式如 http://127.0.0.1:<端口>（回车=直连）: ").strip()
    return s or None


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


def ensure_venv(system_python, proxy=None):
    if venv_ok():
        eprint("[install] venv 已就绪，跳过构建")
        return
    env = dict(os.environ)
    if proxy:
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            env[var] = proxy
        eprint(f"[install] pip 依赖下载走代理 {proxy}")
    eprint("[install] 创建 venv（首次，需几分钟）")
    run([system_python, "-m", "venv", str(VENV_DIR)], check=True)
    run([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"], check=True, env=env)
    eprint("[install] 安装 paddlepaddle + paddleocr（约 1GB，请耐心等待）")
    run([str(VENV_PY), "-m", "pip", "install", "paddlepaddle", "paddleocr"], check=True, env=env)
    if not venv_ok():
        raise SystemExit("[install] venv 构建后 paddleocr 仍不可用")


def ensure_models(config, force=False, model=None, proxy=None):
    mmap = load_models_map()
    name = model or config.get("model") or DEFAULT_CONFIG["model"]
    if name not in mmap:
        raise SystemExit(f"[install] 未知模型: {name}（可用: {', '.join(mmap)}）")
    if model:
        config["model"] = model
    if proxy is not None:
        config["proxy"] = proxy or None
    if model or proxy is not None:
        write_config(config)  # 改动即落盘，即使模型已存在（跳过下载）也保存
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
    env = dict(os.environ)
    if proxy:
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            env[var] = proxy
        eprint(f"[install] 模型下载走代理 {proxy}")
    eprint(f"[install] 下载模型 {name}（首次可能几分钟）")
    r = subprocess.run([str(VENV_PY), "-c", snippet, str(job), str(SKILL_DIR / "models")],
                       env=env, capture_output=True, text=True)
    job.unlink(missing_ok=True)
    if r.returncode != 0 or "MODELS_OK" not in r.stdout:
        raise SystemExit(f"[install] 模型下载失败:\n{r.stdout}\n{r.stderr}")
    config["installed_version"] = name
    write_config(config)


def installed_models():
    """{name: 是否已下载}——按 models.json 候选查 models/official_models/。"""
    mmap = load_models_map()
    out = {}
    base = SKILL_DIR / "models" / "official_models"
    for name, params in mmap.items():
        det = params.get("text_detection_model_name") or f"{name}_det"
        rec = params.get("text_recognition_model_name") or f"{name}_rec"
        out[name] = (base / det).exists() and (base / rec).exists()
    return out


def model_table():
    mmap = load_models_map()
    cfg = read_config()
    inst = installed_models()
    rows = []
    for name in mmap:
        mark = "  [默认]" if name == cfg.get("model") else ""
        st = "已安装" if inst[name] else "未安装"
        rows.append(f"{name} [{st}]{mark} — {mmap[name].get('desc', '')}")
    return rows


def rm_model(name, cfg):
    """删除某模型的缓存文件；若它是默认则回退默认。返回是否删除过。"""
    mmap = load_models_map()
    det = mmap[name].get("text_detection_model_name") or f"{name}_det"
    rec = mmap[name].get("text_recognition_model_name") or f"{name}_rec"
    base = SKILL_DIR / "models" / "official_models"
    removed = False
    for d in (det, rec):
        p = base / d
        if p.exists():
            shutil.rmtree(p)
            print(f"[models] 已删除 {d}")
            removed = True
    if name == cfg.get("model"):
        cfg["model"] = DEFAULT_CONFIG["model"]
        write_config(cfg)
        print(f"[models] 默认模型已回退到 {DEFAULT_CONFIG['model']}")
    if not removed:
        print(f"[models] {name} 未安装，无需删除")
    return removed


def _models_menu():
    mmap = load_models_map()
    if not sys.stdin.isatty():
        print("[models] 非交互，列出如下；命令: models list / set-default|add|rm <模型名>")
        for r in model_table():
            print(f"  {r}")
        return 0
    while True:
        print("\n[models] 模型管理：")
        for i, name in enumerate(mmap, 1):
            print(f"  {i}. {model_table_inst(name)}")
        print("操作: [s]设默认  [d]下载  [r]删除  [q]退出")
        op = _readline("> ").strip().lower()
        if op == "q" or not op:
            return 0
        if op not in ("s", "d", "r"):
            print("无效操作")
            continue
        sel = _readline("输入模型编号: ").strip()
        if not sel.isdigit() or not (1 <= int(sel) <= len(mmap)):
            print("无效编号")
            continue
        name = list(mmap)[int(sel) - 1]
        if op == "s":
            cfg = read_config()
            cfg["model"] = name
            write_config(cfg)
            print(f"[models] 默认模型已设为 {name}（未安装则下次 OCR 自动下载）")
        elif op == "d":
            cfg = read_config()
            p = _readline("代理地址（回车=直连，如 http://127.0.0.1:<端口>）: ").strip() or None
            ensure_models(cfg, model=name, proxy=p)
        elif op == "r":
            rm_model(name, read_config())


def model_table_inst(name, idx=None):
    mmap = load_models_map()
    cfg = read_config()
    inst = installed_models()
    mark = "  [默认]" if name == cfg.get("model") else ""
    st = "已安装" if inst[name] else "未安装"
    prefix = f"{idx}. " if idx else ""
    return f"{prefix}{name} [{st}]{mark} — {mmap[name].get('desc', '')}"


def cmd_models(args):
    mmap = load_models_map()
    cfg = read_config()
    if args.action == "list":
        print("[models] 可用模型：")
        for r in model_table():
            print(f"  {r}")
        print(f"[models] 当前默认: {cfg.get('model')}  proxy={cfg.get('proxy') or '无'}")
        return 0
    if args.name and args.name not in mmap:
        print(f"[models] 未知模型 {args.name}。可用: {', '.join(mmap)}")
        return 1
    if args.action == "set-default":
        cfg["model"] = args.name
        write_config(cfg)
        print(f"[models] 默认模型已设为 {args.name}（未安装则下次 OCR 自动下载）")
        return 0
    if args.action == "add":
        ensure_models(cfg, model=args.name, proxy=args.proxy)
        return 0
    if args.action == "rm":
        rm_model(args.name, cfg)
        return 0
    if args.action == "menu":
        return _models_menu()
    return 0



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
          f"help_hint={cfg.get('help_hint')} proxy={cfg.get('proxy') or '无'} "
          f"manifest_url={cfg.get('manifest_url') or '未配置'}")
    return 0


def cmd_install(args):
    found = find_python()
    if not found:
        print(f"[install] 未检测到可用的 Python（3.8-3.13）。请先安装: {PY_DOWNLOAD_URL}")
        return 2
    system_python, ver = found
    eprint(f"[install] 使用系统 python {ver}")
    cfg = read_config()
    mmap = load_models_map()

    # 1) 代理：一次询问，覆盖后续 pip 依赖与模型下载
    if args.proxy is not None:
        cfg["proxy"] = args.proxy or None
        write_config(cfg)
    elif not cfg.get("proxy"):
        if sys.stdin.isatty():
            p = ask_proxy()
            if p:
                cfg["proxy"] = p
                write_config(cfg)
        else:
            eprint("[install] 未配置代理，下载直连；可用 --proxy 或 /llm-sight-config 配置")
    proxy = cfg.get("proxy")

    # 2) 模型选择：有模型问"用默认还是下其他"，无模型问下载哪个（代理已问过）
    if (SKILL_DIR / "models" / "official_models").exists():
        if sys.stdin.isatty() and not args.model:
            s = _readline(
                f"[install] 已装好 OCR 模型，当前默认是 {cfg.get('model') or DEFAULT_CONFIG['model']}。\n"
                "[install] 直接用默认就行，还是要下载其他模型？（y=用默认 / n=下载其他模型）: "
            ).strip().lower()
            if s.startswith("n"):
                args.model = ask_model(mmap, cfg.get("model") or DEFAULT_CONFIG["model"])
        else:
            eprint("[install] 检测到已有模型，用当前默认；要下载其他模型用 setup.py models add <模型名> 或 /llm-sight-model")
    else:
        if not args.model:
            picked = ask_model(mmap, cfg.get("model") or DEFAULT_CONFIG["model"])
            if picked:
                args.model = picked
            else:
                print(f"[install] 未交互输入，用默认模型 {cfg.get('model') or DEFAULT_CONFIG['model']}"
                      f"（候选: {', '.join(mmap)}；想换用 setup.py install --model X）")

    # 3) 装依赖（venv + pip，走上面确认的代理）
    ensure_venv(system_python, proxy)

    # 4) 装模型（走代理）
    ensure_models(cfg, model=args.model,
                  proxy=args.proxy if args.proxy is not None else proxy)
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
    if args.help_hint is not None:
        cfg["help_hint"] = args.help_hint
    if args.proxy is not None:
        cfg["proxy"] = args.proxy or None
    if args.manifest_url is not None:
        cfg["manifest_url"] = args.manifest_url or None
    write_config(cfg)
    print(f"[config] model={cfg['model']} auto_update={cfg['auto_update']} "
          f"help_hint={cfg.get('help_hint')} proxy={cfg.get('proxy') or '无'} "
          f"manifest_url={cfg.get('manifest_url') or '未配置'}")
    return 0


def cmd_update():
    cfg = read_config()
    return update_check(cfg)


def main():
    ap = argparse.ArgumentParser(description="llm-sight 环境引导器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="完整性检查")
    pi = sub.add_parser("install", help="引导：建 venv、确保模型、装斜杠命令")
    pi.add_argument("--model", help="要下载/使用的模型（默认 PP-OCRv6_medium）")
    pi.add_argument("--proxy", help="模型下载代理地址，如 http://127.0.0.1:<端口>（不给则直连）")
    p = sub.add_parser("config", help="查看/修改配置")
    p.add_argument("--model")
    p.add_argument("--auto-update", type=lambda s: s.lower() in ("1", "true", "on", "yes"))
    p.add_argument("--help-hint", type=lambda s: s.lower() in ("1", "true", "on", "yes"),
                   help="大模型用 skill 时是否提醒 /llm-sight-help（默认 on）")
    p.add_argument("--proxy", help="代理地址，如 http://127.0.0.1:<端口>（空串清除）")
    p.add_argument("--manifest-url", help="更新清单 URL（空串清除）")
    m = sub.add_parser("models", help="模型管理")
    m.add_argument("action", choices=("list", "set-default", "add", "rm", "menu"),
                   nargs="?", default="menu")
    m.add_argument("name", nargs="?")
    m.add_argument("--proxy", help="下载代理地址，如 http://127.0.0.1:<端口>（不给则直连）")
    sub.add_parser("update", help="检查模型更新（手动触发）")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "install":
        return cmd_install(args)
    if args.cmd == "config":
        return cmd_config(args)
    if args.cmd == "models":
        return cmd_models(args)
    if args.cmd == "update":
        return cmd_update()
    return 0


if __name__ == "__main__":
    sys.exit(main())
