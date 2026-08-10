# llm-sight troubleshooting

## Bootstrap, config & updates

Everything is driven by `scripts/setup.py` (runs with any Python 3.8–3.13, pure
stdlib — it is NOT the OCR runtime):

| Command | What it does |
|---|---|
| `python setup.py check` | status: python / venv / models / GPU / config |
| `python setup.py install` | create `.venv` + `pip install rapidocr onnxruntime(-dml)` (~300MB), recommend the default model download (not forced), config GPU prompt, install slash commands |
| `python setup.py config --model-cpu X --model-gpu Y --gpu on\|off --gpu-module install\|remove --auto-update on\|off --proxy URL --manifest-url URL` | read/write `config.json` |
| `python setup.py models list\|set-default\|add\|rm` | model management (with size / accuracy / who-it-fits) |
| `python setup.py update` | check for a newer OCR model via `manifest_url` (proxy-aware); failure is non-blocking |

- **No Python found** → `setup.py` prints the official download link. It never
  auto-installs Python, and never touches a system Python (`install` builds the
  skill's own `.venv` only).
- **Config** lives in `<SKILL_DIR>/config.json` (this machine only, not shipped).
  Defaults: `model_cpu=PP-OCRv6_small`, `model_gpu=PP-OCRv6_medium`,
  `gpu=false`, `gpu_capable=false`, `auto_update=true`, no proxy, no manifest.
- **Model update check** triggers on `/llm-sight-update`. It needs `manifest_url`
  set; without it, it says "not configured" and moves on.
- Models in this skill (name → params in `scripts/models.json`): PP-OCRv6_small
  (CPU default, 31MB) / PP-OCRv6_medium (GPU default, 136MB) / PP-OCRv6_tiny
  (7MB) / PP-OCRv5_server (165MB) / PP-OCRv4_mobile (15MB) /
  PP-OCRv5_cyrillic (18MB, bundled) / PP-OCRv5_korean (23MB) /
  PP-OCRv5_arabic (18MB).

## Environment (the skill's venv)

The skill runs in its own Python 3.12 venv: `<SKILL_DIR>/.venv`, built by
`setup.py install`. Recreate it the same way (one command), or manually:

```bash
python -m venv <SKILL_DIR>/.venv
<SKILL_DIR>/.venv/Scripts/python -m pip install rapidocr onnxruntime
# GPU 模块（可选）:
<SKILL_DIR>/.venv/Scripts/python -m pip install onnxruntime-directml
```

`onnxruntime-directml` replaces `onnxruntime` (both provide the `onnxruntime`
module). Manage the swap via `setup.py config --gpu-module install|remove`.

## Models & cache

- Models are **PP-OCRv6** (ONNX) from **modelscope.cn** (RapidAI/RapidOCR), on
  first use, cached in `<SKILL_DIR>/models/rapidocr/` (det + rec + cls onnx).
  Nothing outside the skill dir.
- **Force a re-download:** delete the `.onnx` file under `models/rapidocr/`.
- **Model not cached → `ocr.py` asks before downloading** (never silent).

## Languages (v6 model)

PP-OCRv6 det/rec supports **ch / en / chinese_cht / japan** (the v6 rec also reads
Latin-script languages under `ch`). Other languages use per-language models in the
list: **PP-OCRv5_cyrillic** (russian, bundled in `_standard`/`_full`),
**PP-OCRv5_korean** / **PP-OCRv5_arabic** (download on demand; detection of these
scripts can be unstable — test before relying on them). Pick the model via
`/llm-sight-model`; `--lang` on a v6 model with an unsupported language errors
with a clear message.

## GPU support (DirectML — works on Blackwell)

- **Engine is onnxruntime, not paddle.** paddle's CUDA path does NOT work on
  RTX 50 series (Blackwell, sm_120): paddle cu126 wheels produce garbage output
  (cuDNN/内核 mismatch). This skill moved to **DirectML** (`onnxruntime-directml`),
  which uses the D3D12 hardware abstraction and works on any DX12 GPU,
  NVIDIA RTX 50 series included.
- **`gpu` config** enables DML (CPU falls back if the module is absent or the
  hardware can't run it).
- **Hardware gate** (`gpu_capable`) is detected via `D3D11CreateDevice` with the
  hardware driver type — it works even when the GPU module is not installed, so
  a removed module can always be reinstalled.
- **If the module is installed but the machine can't use GPU**, `ocr.py` and
  `setup.py` suggest deleting the module to free ~150MB, and re-downloading
  after switching to a supported device.
- **First install**: prompts to enable/install GPU only when a capable GPU is
  detected. Installing the module always shows a confirmation prompt.

## Performance notes

- CPU + v6 medium: **~60-80s per image** (the medium rec model is heavy on
  onnxruntime CPU). Use the small model on CPU, or enable GPU.
- GPU (DML) + v6 medium: **~0.3-1s** per image. GPU + v6 small: ~0.1s.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | success (text may be empty) | — |
| 2 | rapidocr not installed | run `setup.py install` |
| 3 | image file/URL unreachable or unreadable | check the path/URL |
| 4 | OCR init or runtime error | read stderr; see below |

## Common errors

- **`no such file: ...`** — the image path doesn't exist. Expand `~`/relative
  paths against the working directory before passing.
- **Empty result / `(no text detected)`** — genuinely no readable text, or very
  low confidence. Not an error; report it honestly.
- **`Unsupported rec.lang_type='korean' for PP-OCRv6 ... model.`** — v6 supports
  only ch/en/chinese_cht/japan. Switch to a v4/v5 model for other languages.
- **`The truth value of an array ... ambiguous`** — a regression in ocr.py's
  result handling; report it (should not happen on current code).
- **Encoding garbage in output** — the wrapper forces UTF-8 on stdout; if you
  still see mojibake, your terminal is decoding GBK. Read the bytes as UTF-8.
- **`ImportError` on `rapidocr`/`onnxruntime`** — wrong python was used. Always
  invoke with `<SKILL_DIR>/.venv/Scripts/python.exe`, never a bare `python`.

## Verification

Sanity-check the install from the venv:

```bash
<SKILL_DIR>/.venv/Scripts/python -c "import rapidocr; import onnxruntime; print('ok', onnxruntime.get_available_providers())"
```
