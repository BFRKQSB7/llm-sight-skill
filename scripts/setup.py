#!/usr/bin/env python3
"""llm-sight 环境引导器：check / install / config / models / update。

用系统 python 跑（纯 stdlib，零依赖）。skill 的 .venv 是依赖载体，由本脚本构建。
引擎 = rapidocr（PP-OCRv6 ONNX + onnxruntime）；GPU 加速 = onnxruntime-directml
（DirectML），可选模块。所有 OCR 工作文件（venv/models/config/tmp）都在 skill 目录内。
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
MODEL_ROOT = SKILL_DIR / "models" / "rapidocr"
CLS_FILE = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
GPU_MARKER = SKILL_DIR / "gpu_module.marker"  # _full 版本带此标记 → setup 默认装 DirectML
COMMANDS_SRC = Path(__file__).resolve().parent.parent / "commands"
COMMANDS_DST = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~")) / ".claude" / "commands"

PY_DOWNLOAD_URL = "https://www.python.org/downloads/"
PY_MIN, PY_MAX = (3, 8), (3, 14)

GPU_MODULE_SIZE_MB = 150  # onnxruntime-directml 约 150MB（实际随包）

DEFAULT_CONFIG = {
    "model_cpu": "PP-OCRv6_small",
    "model_gpu": "PP-OCRv6_medium",
    "gpu": False,
    "gpu_capable": False,
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


def read_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            eprint(f"[config] 读取 config.json 失败（用默认）: {e}")
    # 兼容旧版单一 model 字段
    if cfg.get("model"):
        if not cfg.get("model_cpu"):
            cfg["model_cpu"] = cfg["model"]
        if not cfg.get("model_gpu"):
            cfg["model_gpu"] = cfg["model"]
        cfg.pop("model", None)
    return cfg


def write_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    eprint(f"[config] 已写入 {CONFIG}")


def run(cmd, **kw):
    eprint("[run] " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, **kw)


def proxied_env(proxy):
    env = dict(os.environ)
    if proxy:
        for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            env[var] = proxy
        eprint(f"[net] 网络走代理 {proxy}")
    return env


# ---------- python / venv ----------

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
        r = subprocess.run([str(VENV_PY), "-c", "import rapidocr", ],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except subprocess.SubprocessError:
        return False


def gpu_hardware_capable():
    """符合要求的显卡判定：能创建硬件 D3D11 设备（现代显卡皆满足，隐含 DX12）。
    不依赖 onnxruntime-directml 包——删除模块后仍能检测，保证可重装。"""
    if os.name != "nt":
        return False
    try:
        import ctypes
        d3d11 = ctypes.WinDLL("d3d11.dll")
        d3d11.D3D11CreateDevice.restype = ctypes.c_long
        device = ctypes.c_void_p()
        ctx = ctypes.c_void_p()
        fl = ctypes.c_uint(0xB000)  # D3D_FEATURE_LEVEL_11_0
        # pAdapter=NULL, DriverType=D3D_DRIVER_TYPE_HARDWARE(1), Flags=0,
        # pFeatureLevels, FeatureLevels=1, SDKVersion=7, ppDevice, pFLOut=NULL, ppContext
        hr = d3d11.D3D11CreateDevice(
            None, 1, 0, 0, ctypes.byref(fl), 1, 7,
            ctypes.byref(device), None, ctypes.byref(ctx))
        return hr == 0
    except Exception:
        return False


def venv_has_dml_module():
    """venv 里是否装了 onnxruntime-directml。"""
    if not VENV_PY.exists():
        return False
    try:
        r = subprocess.run(
            [str(VENV_PY), "-c",
             "import importlib.metadata as m\n"
             "m.distribution('onnxruntime-directml'); print('YES')"],
            capture_output=True, text=True, timeout=60)
        return "YES" in r.stdout
    except subprocess.SubprocessError:
        return False


def venv_gpu_status():
    """返回 (硬件符合要求, 模块已安装, DML 可用=两者皆真)。"""
    capable = gpu_hardware_capable()
    module = venv_has_dml_module()
    return capable, module, (capable and module)


def ensure_venv(system_python, proxy, want_gpu_module=False):
    if venv_ok():
        eprint("[install] venv 已就绪，跳过构建")
        return
    env = proxied_env(proxy)
    eprint("[install] 创建 venv（首次，需几分钟）")
    run([system_python, "-m", "venv", str(VENV_DIR)], check=True)
    run([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip"], check=True, env=env)
    if want_gpu_module:
        eprint("[install] 安装 rapidocr + onnxruntime-directml（含 GPU 模块，约 450MB，请耐心等待）")
        run([str(VENV_PY), "-m", "pip", "install", "rapidocr", "onnxruntime-directml"], check=True, env=env)
    else:
        eprint("[install] 安装 rapidocr + onnxruntime（约 300MB，请耐心等待）")
        run([str(VENV_PY), "-m", "pip", "install", "rapidocr", "onnxruntime"], check=True, env=env)
    if not venv_ok():
        raise SystemExit("[install] venv 构建后 rapidocr 仍不可用")


def install_gpu_module(proxy):
    """装 onnxruntime-directml（替换 onnxruntime）。返回是否成功。"""
    if not VENV_PY.exists():
        raise SystemExit("[gpu] 缺 venv，请先跑 install")
    env = proxied_env(proxy)
    eprint(f"[gpu] 安装 GPU 加速模块（onnxruntime-directml，约 {GPU_MODULE_SIZE_MB}MB）")
    r = run([str(VENV_PY), "-m", "pip", "install", "onnxruntime-directml"], env=env)
    if r.returncode != 0:
        raise SystemExit("[gpu] 安装失败")
    return True


def remove_gpu_module(proxy):
    """卸载 onnxruntime-directml，装回 onnxruntime（CPU）。"""
    if not VENV_PY.exists():
        raise SystemExit("[gpu] 缺 venv，请先跑 install")
    env = proxied_env(proxy)
    eprint("[gpu] 卸载 onnxruntime-directml，装回 onnxruntime（CPU）")
    r = run([str(VENV_PY), "-m", "pip", "uninstall", "-y", "onnxruntime-directml"], env=env)
    r2 = run([str(VENV_PY), "-m", "pip", "install", "onnxruntime"], env=env)
    if r.returncode != 0 or r2.returncode != 0:
        raise SystemExit("[gpu] 删除模块失败")


# ---------- models ----------

def model_cached(name):
    mmap = load_models_map()
    m = mmap.get(name) or {}
    if not m.get("det_file"):
        return True
    files = [m.get("det_file"), m.get("rec_file"), CLS_FILE]
    return all(f and (MODEL_ROOT / f).exists() for f in files)


def installed_models():
    mmap = load_models_map()
    return {name: model_cached(name) for name in mmap}


def model_line(name, cfg=None, inst=None):
    mmap = load_models_map()
    m = mmap[name]
    marks = []
    if cfg:
        if name == cfg.get("model_cpu"):
            marks.append("CPU默认")
        if name == cfg.get("model_gpu"):
            marks.append("GPU默认")
    tag = f" [{'/'.join(marks)}]" if marks else ""
    st = "已装" if (inst is None or inst[name]) else "未装"
    return (f"{name} [{st}]{tag} — {m['size_mb']}MB · "
            f"识别率 det {m['det_hmean']}%/rec {m['rec_acc']}% · 语言 {m.get('langs', '?')} · {m['who']}")


def model_table(cfg=None):
    inst = installed_models()
    return [model_line(name, cfg, inst) for name in load_models_map()]


def ensure_models(cfg, name, proxy=None):
    """下载指定模型到 models/rapidocr（warmup 触发 rapidocr 下载）。"""
    mmap = load_models_map()
    if name not in mmap:
        raise SystemExit(f"[install] 未知模型: {name}（可用: {', '.join(mmap)}）")
    if proxy is not None:
        cfg["proxy"] = proxy or None
        write_config(cfg)
    if model_cached(name):
        eprint(f"[models] {name} 已下载，跳过")
        return
    if not VENV_PY.exists():
        raise SystemExit("[models] 缺 venv，请先跑 install")
    m = mmap[name]
    snippet = (
        "import json,sys,os\n"
        "from rapidocr import RapidOCR\n"
        "from rapidocr.utils.typings import ModelType, OCRVersion, LangRec\n"
        "p=json.load(open(sys.argv[1],encoding='utf-8'))\n"
        "params={'Global.model_root_dir':sys.argv[2],\n"
        " 'Det.ocr_version':OCRVersion(p['ocr_version']),'Det.model_type':ModelType(p['model_type']),\n"
        " 'Rec.ocr_version':OCRVersion(p['ocr_version']),'Rec.model_type':ModelType(p['model_type']),\n"
        " 'Rec.lang_type':LangRec('ch'),'EngineConfig.onnxruntime.use_dml':False}\n"
        "RapidOCR(params=params)\n"
        "print('MODELS_OK')\n"
    )
    tmp = SKILL_DIR / "tmp"
    tmp.mkdir(exist_ok=True)
    job = tmp / "warmup.json"
    job.write_text(json.dumps({"ocr_version": m["ocr_version"], "model_type": m["model_type"]},
                              ensure_ascii=False), encoding="utf-8")
    env = proxied_env(proxy or cfg.get("proxy"))
    eprint(f"[models] 下载模型 {name}（{m['size_mb']}MB，首次可能几分钟）")
    r = subprocess.run([str(VENV_PY), "-c", snippet, str(job), str(MODEL_ROOT)],
                       env=env, capture_output=True, text=True, timeout=1800)
    job.unlink(missing_ok=True)
    if r.returncode != 0 or "MODELS_OK" not in r.stdout:
        raise SystemExit(f"[models] 模型下载失败:\n{r.stdout}\n{r.stderr}")
    cfg["installed_version"] = name
    write_config(cfg)


def rm_model(name, cfg):
    """删除某模型的缓存文件；若它是默认则回退对应默认。"""
    mmap = load_models_map()
    m = mmap.get(name)
    if not m:
        print(f"[models] 未知模型 {name}")
        return False
    removed = False
    for key in ("det_file", "rec_file"):
        p = MODEL_ROOT / m[key]
        if p.exists():
            p.unlink()
            print(f"[models] 已删除 {m[key]}")
            removed = True
    if name == cfg.get("model_cpu"):
        cfg["model_cpu"] = DEFAULT_CONFIG["model_cpu"]
        write_config(cfg)
        print(f"[models] CPU 默认模型已回退到 {DEFAULT_CONFIG['model_cpu']}")
    if name == cfg.get("model_gpu"):
        cfg["model_gpu"] = DEFAULT_CONFIG["model_gpu"]
        write_config(cfg)
        print(f"[models] GPU 默认模型已回退到 {DEFAULT_CONFIG['model_gpu']}")
    if not removed:
        print(f"[models] {name} 未安装，无需删除")
    return removed


def ask_model(mmap, default):
    """交互询问下载哪个模型；空输入/非交互返回 None（由调用方用默认）。"""
    if not sys.stdin.isatty():
        return None
    print("需要下载一个 OCR 模型才能识别图片文字（首次一次性）。可选：")
    for i, name in enumerate(mmap, 1):
        print(f"  {i}. {model_line(name)}")
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
    print("接下来要下载依赖（约 300MB）和 OCR 模型（数百 MB）。")
    print("如果网络访问下载源需要代理，请填代理地址；不需要则直接回车（直连下载）。")
    print("代理地址会保存到本机 config，之后更新检查也用它。")
    s = _readline("代理地址，格式如 http://127.0.0.1:<端口>（回车=直连）: ").strip()
    return s or None


# ---------- GPU 交互 ----------

def gpu_enable_prompt(cfg, proxy):
    """首次安装后的 GPU 提示：仅硬件符合要求时才弹。返回更新后的 cfg。"""
    capable, module, dml = venv_gpu_status()
    cfg["gpu_capable"] = capable
    if not capable:
        eprint("[install] 未检测到可用 DirectML 设备，跳过 GPU 配置")
        write_config(cfg)
        return cfg
    if not sys.stdin.isatty():
        eprint("[install] 检测到可用 DirectML 设备；非交互，未启用 GPU（可用 config --gpu on 开启）")
        write_config(cfg)
        return cfg
    eprint("[install] 检测到你的显卡支持 GPU 加速（DirectML）。")
    if module:
        ans = _readline("[install] 是否启用 GPU 加速？（说明：识图大幅变快，GPU 默认用 v6 medium 更准；"
                        "会修改 config 的 gpu 字段。y=启用 / N=不用）: ").strip().lower()
        if ans.startswith("y"):
            cfg["gpu"] = True
            print("[install] GPU 加速已启用（/llm-sight-config --gpu off 可关闭）")
    else:
        ans = _readline(
            f"[install] 是否安装并启用 GPU 加速模块（onnxruntime-directml，约 {GPU_MODULE_SIZE_MB}MB，"
            "会修改 config 的 gpu 字段，可随时删除）？(y/N): ").strip().lower()
        if ans.startswith("y"):
            install_gpu_module(proxy or cfg.get("proxy"))
            cfg["gpu"] = True
            print("[install] GPU 模块已安装并启用（/llm-sight-config --gpu-module remove 可删除）")
    write_config(cfg)
    return cfg


# ---------- commands ----------

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
    installed = config.get("installed_version")
    if latest and installed and latest != installed:
        print(f"[update] 检测到新版本模型: {installed} -> {latest}（setup.py models set-default {latest} 可切换）")
    elif latest and not installed:
        print(f"[update] 推荐模型: {latest}")
    else:
        print(f"[update] 已是最新（{installed}）")
    config["last_check"] = time.time()
    write_config(config)
    return 0


# ---------- subcommands ----------

def cmd_check():
    print("[status] llm-sight 环境检查（引擎: rapidocr / onnxruntime）")
    print(f"[status] skill 目录: {SKILL_DIR}")
    found = find_python()
    if found:
        print(f"[status] python: {found[1]}")
    else:
        print(f"[status] python: 未找到（请安装 Python 3.8-3.13: {PY_DOWNLOAD_URL}）")
    print(f"[status] venv: {'ok' if venv_ok() else '缺失/不可用'}")
    cfg = read_config()
    capable, module, dml = venv_gpu_status()
    print(f"[status] GPU 模块: {'已安装' if module else '未安装'} | "
          f"DirectX12 显卡: {'符合要求' if capable else '不支持'} | 启用: {'是' if cfg.get('gpu') else '否'}")
    print(f"[status] config: model_cpu={cfg.get('model_cpu')} model_gpu={cfg.get('model_gpu')} "
          f"auto_update={cfg.get('auto_update')} help_hint={cfg.get('help_hint')} "
          f"proxy={cfg.get('proxy') or '无'} manifest_url={cfg.get('manifest_url') or '未配置'}")
    print("[status] 模型：")
    for line in model_table(cfg):
        print(f"  {line}")
    return 0


def cmd_install(args):
    found = find_python()
    if not found:
        print(f"[install] 未检测到可用的 Python（3.8-3.13）。请先安装: {PY_DOWNLOAD_URL}")
        return 2
    system_python, ver = found
    eprint(f"[install] 使用系统 python {ver}")
    cfg = read_config()
    want_gpu = GPU_MARKER.exists()  # _full 版本默认带 GPU 模块
    if want_gpu:
        eprint("[install] 检测到 _full 版本标记，默认包含 GPU 加速模块")

    # 1) 代理：一次询问
    if args.proxy is not None:
        cfg["proxy"] = args.proxy or None
        write_config(cfg)
    elif not cfg.get("proxy") and sys.stdin.isatty():
        p = ask_proxy()
        if p:
            cfg["proxy"] = p
            write_config(cfg)
    proxy = cfg.get("proxy")

    # 2) 装依赖（venv，full 版默认装 DirectML）
    ensure_venv(system_python, proxy, want_gpu_module=want_gpu)

    # 3) GPU 提示（仅 DML 可用时弹）
    cfg = gpu_enable_prompt(cfg, proxy)

    # 4) 模型：推荐下载默认（不强求）
    capable, module, dml = venv_gpu_status()
    default_model = cfg.get("model_gpu") if dml else cfg.get("model_cpu")
    if not model_cached(default_model):
        if sys.stdin.isatty():
            mmap = load_models_map()
            m = mmap[default_model]
            ans = _readline(
                f"[install] 推荐下载默认模型 {default_model}（{m['size_mb']}MB · "
                f"识别率 det {m['det_hmean']}%/rec {m['rec_acc']}% · 语言 {m.get('langs', '?')}）。下载吗？"
                f"(y=下载 / N=跳过，首次识图再下载）: "
            ).strip().lower()
            if ans.startswith("y"):
                ensure_models(cfg, default_model, proxy)
        else:
            eprint(f"[install] 默认模型 {default_model} 未下载，跳过（首次识图时询问下载）")
    else:
        eprint(f"[install] 默认模型 {default_model} 已就绪")

    install_commands()
    print("[install] 完成。可用 /llm-sight-status 查看状态")
    return 0


def cmd_config(args):
    cfg = read_config()
    mmap = load_models_map()

    changed = any(v is not None for v in (
        args.model_cpu, args.model_gpu, args.auto_update, args.help_hint,
        args.proxy, args.manifest_url, args.gpu, args.gpu_module))
    if not changed:
        # 无参数 → 显示配置面板（含模型大小与已下载列表）
        capable, module, dml = venv_gpu_status()
        inst = installed_models()
        inst_list = [f"{n}({mmap[n]['size_mb']}MB)" for n in mmap if inst[n]]
        print("[config] 当前配置：")
        print(f"  model_cpu = {cfg.get('model_cpu')}"
              f" ({mmap.get(cfg.get('model_cpu'), {}).get('size_mb', '?')}MB)")
        print(f"  model_gpu = {cfg.get('model_gpu')}"
              f" ({mmap.get(cfg.get('model_gpu'), {}).get('size_mb', '?')}MB)")
        print(f"  gpu = {'on' if cfg.get('gpu') else 'off'} | gpu_capable = {'是' if capable else '否'} | "
              f"gpu_module = {'已装' if module else '未装'}")
        print(f"  auto_update = {cfg.get('auto_update')} | proxy = {cfg.get('proxy') or '无'} | "
              f"manifest_url = {cfg.get('manifest_url') or '未配置'}")
        print(f"[config] 已下载模型（体积）：{('、'.join(inst_list)) if inst_list else '无'}")
        print("[config] 可用模型：")
        for line in model_table(cfg):
            print(f"  {line}")
        print("[config] 管理模型（下载/删除/设默认）用 /llm-sight-model 或 models menu；")
        print("[config] 改设置加参数，如 --model-cpu X --model-gpu Y --gpu on|off --gpu-module install|remove")
        return 0

    for attr, val in (("model_cpu", args.model_cpu), ("model_gpu", args.model_gpu)):
        if val:
            if val not in mmap:
                print(f"[config] 未知模型 {val}。可用: {', '.join(mmap)}")
                return 1
            cfg[attr] = val
    if args.auto_update is not None:
        cfg["auto_update"] = args.auto_update
    if args.help_hint is not None:
        cfg["help_hint"] = args.help_hint
    if args.proxy is not None:
        cfg["proxy"] = args.proxy or None
    if args.manifest_url is not None:
        cfg["manifest_url"] = args.manifest_url or None

    # GPU 开关 / 模块管理（用户显式操作 → 记 gpu_explicit，首次调用不再自动覆盖）
    if args.gpu is not None or args.gpu_module:
        cfg["gpu_explicit"] = True
    if args.gpu is not None:
        capable, module, dml = venv_gpu_status()
        if args.gpu:
            if not capable:
                print("[config] 当前设备不支持 DirectML（GPU 加速），无法启用。")
                if module:
                    print("[config] 建议删除 GPU 模块释放空间；更换支持 DirectML 的设备后再下载：")
                    print("[config]   config --gpu-module remove")
            elif not module:
                print("[config] GPU 加速模块未安装。先安装：config --gpu-module install（会再次检测并提示）")
            else:
                cfg["gpu"] = True
        else:
            cfg["gpu"] = False
    if args.gpu_module:
        action = args.gpu_module
        if action == "install":
            capable, module, dml = venv_gpu_status()
            if not capable:
                print("[config] 当前设备不支持 DirectML，建议不要安装 GPU 模块；")
                print("[config] 更换支持 DirectML 的设备后再安装。")
                return 1
            if sys.stdin.isatty():
                ans = _readline(
                    f"[config] 安装 GPU 加速模块（onnxruntime-directml，约 {GPU_MODULE_SIZE_MB}MB，"
                    "替换 onnxruntime；可随时删除释放空间）。确认安装？(y/N): ").strip().lower()
                if not ans.startswith("y"):
                    print("[config] 已取消")
                    return 0
            install_gpu_module(proxy=cfg.get("proxy"))
            cfg["gpu"] = True
        elif action == "remove":
            if sys.stdin.isatty():
                ans = _readline(
                    "[config] 删除 GPU 加速模块（卸载 onnxruntime-directml，装回 CPU 版，释放约 "
                    f"{GPU_MODULE_SIZE_MB}MB；GPU 加速将关闭）。确认删除？(y/N): ").strip().lower()
                if not ans.startswith("y"):
                    print("[config] 已取消")
                    return 0
            remove_gpu_module(proxy=cfg.get("proxy"))
            cfg["gpu"] = False
        capable, module, dml = venv_gpu_status()
        cfg["gpu_capable"] = capable

    write_config(cfg)
    capable, module, dml = venv_gpu_status()
    print(f"[config] model_cpu={cfg['model_cpu']} model_gpu={cfg['model_gpu']} "
          f"gpu={'on' if cfg.get('gpu') else 'off'} gpu_capable={'是' if capable else '否'} "
          f"gpu_module={'已装' if module else '未装'} auto_update={cfg.get('auto_update')} "
          f"proxy={cfg.get('proxy') or '无'}")
    return 0


def cmd_models(args):
    mmap = load_models_map()
    cfg = read_config()
    if args.action == "list":
        print("[models] 可用模型：")
        for line in model_table(cfg):
            print(f"  {line}")
        inst = installed_models()
        inst_list = [f"{n}({mmap[n]['size_mb']}MB)" for n in mmap if inst[n]]
        print(f"[models] 已下载（体积）：{('、'.join(inst_list)) if inst_list else '无'}")
        print(f"[models] 默认: CPU={cfg.get('model_cpu')} GPU={cfg.get('model_gpu')} "
              f"gpu={'on' if cfg.get('gpu') else 'off'} proxy={cfg.get('proxy') or '无'}")
        return 0
    if args.name and args.name not in mmap:
        print(f"[models] 未知模型 {args.name}。可用: {', '.join(mmap)}")
        return 1
    if args.action == "set-default":
        if args.cpu:
            cfg["model_cpu"] = args.name
        if args.gpu:
            cfg["model_gpu"] = args.name
        if not (args.cpu or args.gpu):
            cfg["model_cpu"] = cfg["model_gpu"] = args.name
        write_config(cfg)
        print(f"[models] 默认模型已设为 {args.name}（未下载则首次识图时询问下载）")
        return 0
    if args.action == "add":
        ensure_models(cfg, args.name, args.proxy)
        return 0
    if args.action == "rm":
        rm_model(args.name, cfg)
        return 0
    if args.action == "menu":
        return _models_menu()
    return 0


def _models_menu():
    mmap = load_models_map()
    if not sys.stdin.isatty():
        print("[models] 非交互，列出如下；命令: models list / set-default|add|rm <模型名> [--cpu|--gpu]")
        for r in model_table(read_config()):
            print(f"  {r}")
        return 0
    while True:
        cfg = read_config()
        print("\n[models] 模型管理：")
        for i, name in enumerate(mmap, 1):
            print(f"  {i}. {model_line(name, cfg)}")
        print("操作: [s]设默认(CPU+GPU)  [c]设CPU默认  [g]设GPU默认  [d]下载  [r]删除  [q]退出")
        op = _readline("> ").strip().lower()
        if op == "q" or not op:
            return 0
        if op not in ("s", "c", "g", "d", "r"):
            print("无效操作")
            continue
        sel = _readline("输入模型编号: ").strip()
        if not sel.isdigit() or not (1 <= int(sel) <= len(mmap)):
            print("无效编号")
            continue
        name = list(mmap)[int(sel) - 1]
        if op == "s":
            cfg["model_cpu"] = cfg["model_gpu"] = name
            write_config(cfg)
            print(f"[models] 默认模型已设为 {name}（CPU+GPU）")
        elif op in ("c", "g"):
            cfg["model_cpu" if op == "c" else "model_gpu"] = name
            write_config(cfg)
            print(f"[models] {'CPU' if op == 'c' else 'GPU'} 默认模型已设为 {name}")
        elif op == "d":
            p = _readline("代理地址（回车=用 config，如 http://127.0.0.1:<端口>）: ").strip() or None
            ensure_models(cfg, name, p)
        elif op == "r":
            rm_model(name, cfg)


def cmd_update():
    return update_check(read_config())


def main():
    ap = argparse.ArgumentParser(description="llm-sight 环境引导器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="完整性检查")
    pi = sub.add_parser("install", help="引导：建 venv、配置 GPU、确保模型、装斜杠命令")
    pi.add_argument("--model", help="要下载/使用的模型")
    pi.add_argument("--proxy", help="代理地址，如 http://127.0.0.1:<端口>（不给则直连）")
    p = sub.add_parser("config", help="查看/修改配置")
    p.add_argument("--model-cpu")
    p.add_argument("--model-gpu")
    p.add_argument("--gpu", type=lambda s: s.lower() in ("1", "true", "on", "yes"),
                   help="启用(on)/停用(off) GPU 加速")
    p.add_argument("--gpu-module", choices=("install", "remove"),
                   help="安装/删除 GPU 加速模块（onnxruntime-directml）")
    p.add_argument("--auto-update", type=lambda s: s.lower() in ("1", "true", "on", "yes"))
    p.add_argument("--help-hint", type=lambda s: s.lower() in ("1", "true", "on", "yes"),
                   help="大模型用 skill 时是否提醒 /llm-sight-help（默认 on）")
    p.add_argument("--proxy", help="代理地址（空串清除）")
    p.add_argument("--manifest-url", help="更新清单 URL（空串清除）")
    m = sub.add_parser("models", help="模型管理")
    m.add_argument("action", choices=("list", "set-default", "add", "rm", "menu"),
                   nargs="?", default="menu")
    m.add_argument("name", nargs="?")
    m.add_argument("--cpu", action="store_true", help="仅设 CPU 默认")
    m.add_argument("--gpu", action="store_true", help="仅设 GPU 默认")
    m.add_argument("--proxy", help="下载代理地址")
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
