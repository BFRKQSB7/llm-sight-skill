# llm-sight troubleshooting

## Bootstrap, config & updates

Everything is driven by `scripts/setup.py` (runs with any Python 3.8–3.13, pure
stdlib — it is NOT the OCR runtime):

| Command | What it does |
|---|---|
| `python setup.py check` | status: python / venv / models / config |
| `python setup.py install` | create `.venv` + `pip install paddlepaddle paddleocr` (~1GB), ensure models, install slash commands to `~/.claude/commands/` |
| `python setup.py config --model X --auto-update on\|off --proxy URL --manifest-url URL` | read/write `config.json` |
| `python setup.py update` | check for a newer OCR model via `manifest_url` (proxy-aware); failure is non-blocking |

- **No Python found** → `setup.py` prints the official download link. It never
  auto-installs Python, and never touches a system Python (`install` builds the
  skill's own `.venv` only).
- **Config** lives in `<SKILL_DIR>/config.json` (this machine only, not shipped).
  Defaults: `model=PP-OCRv6_medium`, `auto_update=true`, no proxy, no manifest.
- **Model update check** triggers on `/llm-sight-update`, and automatically when an
  `ocr.py` init fails (if `auto_update` is on). It needs `manifest_url` set;
  without it, it says "not configured" and moves on.
- Models in this skill: PP-OCRv6_medium (default) / PP-OCRv6_tiny /
  PP-OCRv5_mobile / PP-OCRv5_server / PP-OCRv4_mobile (names → params in
  `scripts/models.json`).

## Environment (the skill's venv)

The skill runs in its own Python 3.12 venv: `<SKILL_DIR>/.venv`, built by
`setup.py install`. Recreate it the same way (one command), or manually:

```bash
python -m venv <SKILL_DIR>/.venv
<SKILL_DIR>/.venv/Scripts/python -m pip install paddlepaddle paddleocr
```

## Model downloads & cache

- Models are **PP-OCRv6** (default) and come from **HuggingFace** (`PaddlePaddle`
  org) on the first run, then are cached.
- Cache lives **inside the skill dir**: `<SKILL_DIR>/models`
  (set via the `PADDLE_PDX_CACHE_HOME` env var in `scripts/ocr.py`). Nothing is
  written to `~/.paddlex`.
- First run takes minutes (a few hundred MB). Later runs reuse the cache.
- **HuggingFace blocked (common in CN networks):** the wrapper keeps whatever
  `HF_ENDPOINT` you set. If downloads stall/fail, set
  `HF_ENDPOINT=https://hf-mirror.com` in the environment before running.
- **Force a re-download:** delete the model folder under
  `<SKILL_DIR>/models/official_models/`, e.g. `PP-OCRv6_medium_det`.

## Known bug: CPU + oneDNN crashes (fixed in ocr.py)

PaddlePaddle 3.3/3.x CPU inference with oneDNN (MKLDNN) enabled hits a PIR
executor bug:

```
ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]
```

`scripts/ocr.py` passes `enable_mkldnn=False` to `PaddleOCR()` to route around
it. Don't "fix" this unless you're on a paddle version where the bug is gone;
the tradeoff is a modest CPU speed loss, acceptable for this use case.

## GPU support（Windows + Blackwell 实测）

- **`device=auto`:** 只有当 paddle 编译含 CUDA 且 `paddle.device.cuda.device_count() > 0`
  时才启用 GPU，否则静默回退 CPU。
- **Windows + Blackwell（RTX 50 系, sm_120）:** cu126 GPU 轮子**能**在 Blackwell 上
  加载并识别设备（CC 12.0），但实际推理**不可用**：Paddle cu126 用 cuDNN 9.9 编译，
  进程里解析到的却是 cuDNN 9.5，版本错配导致识别输出全是乱码，且比 CPU 慢得多
  （简单图 5 分半 vs CPU ~10 秒）。**建议用 CPU。** 想追 GPU 需让 paddle 进程加载
  匹配的 cuDNN 9.9 dll，改动成本高、收益小，暂不处理。
- **受支持的 GPU:** 按官方索引装对应 GPU 轮子即可让 `device=auto` 用上，但请先确认
  cuDNN 版本与 Paddle 编译一致。

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | success (text may be empty) | — |
| 2 | paddleocr not installed | run the printed `pip install` |
| 3 | image file/URL unreachable or unreadable | check the path/URL |
| 4 | PaddleOCR init or runtime error | read stderr; see below |

## Common errors

- **`no such file: ...`** — the image path doesn't exist. Expand `~`/relative
  paths against the working directory before passing.
- **Empty result / `(no text detected)`** — genuinely no readable text, or very
  low confidence. Not an error; report it honestly.
- **Slow run after first** — CPU inference on a large image can take seconds;
  that's normal. Blurry/gigapixel scans are the worst case.
- **Encoding garbage in output** — the wrapper forces UTF-8 on stdout; if you
  still see mojibake, your terminal is decoding GBK. Read the bytes as UTF-8.
- **`ImportError` on `paddle`** — wrong python was used. Always invoke with
  `<SKILL_DIR>/.venv/Scripts/python.exe`, never a bare `python`.

## Alternative inference engines

`ocr.py` supports `--engine onnxruntime` / `--engine transformers`. These skip
the paddlepaddle dependency and sidestep the oneDNN bug, but need extra installs
in the skill venv and are slower to set up; stick with the default `paddle`
engine unless you have a specific reason.

## Verification

Sanity-check the install from the venv:

```bash
<SKILL_DIR>/.venv/Scripts/python -c "import paddleocr; import paddle; print(paddleocr.__version__, paddle.__version__)"
```
