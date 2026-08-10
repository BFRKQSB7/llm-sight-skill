---
name: llm-sight
description: >-
  Extract text from images, screenshots, and pictures using PP-OCRv6 models
  (rapidocr, ONNX + onnxruntime). USE THIS whenever the user hands you an image,
  screenshot, photo, scan, or picture and expects you to read the text in it —
  to transcribe, quote, translate, summarize, or act on what the image says.
  This matters most when you are a non-multimodal model and cannot see the image
  directly: do NOT guess what the image shows, run the OCR script and read its
  output. If you try to `read` an image file and it fails, errors, or shows only
  binary/illegible content, STOP retrying `read` and use this skill instead.
  Triggers on: OCR, 识别图片文字, 图片里写了什么, 提取图片文字, 截图里的文字,
  字幕, transcribe image, read text from screenshot, what does this image say,
  convert image to text, parse text out of a picture. Also fires when the user
  pastes an image path/URL and asks any question whose answer depends on the
  image's content.
---

# llm-sight: read text out of images with PP-OCRv6 (rapidocr)

You can't see the image, but you can extract its text reliably. This skill turns
an image into plain text via rapidocr (PP-OCRv6 ONNX models on onnxruntime).
Use the extracted text as ground truth for whatever the user asked — never guess
what the image shows.

## The one command

```bash
"<SKILL_DIR>/.venv/Scripts/python.exe" "<SKILL_DIR>/scripts/ocr.py" <image> [options]
```

`<SKILL_DIR>` = this skill's own directory (the folder containing `SKILL.md`).
Common flags:

| Flag | Meaning | Default |
|---|---|---|
| `--lang ch` | language (ch, en, chinese_cht, japan via the v6 model; russian via PP-OCRv5_cyrillic, korean via PP-OCRv5_korean, arabic via PP-OCRv5_arabic — pick those models in `/llm-sight-model`) | `ch` |
| `--format text` | text = one recognized line per stdout line | `text` |
| `--format json` | structured: texts + confidence scores + box coordinates | — |
| `--device auto` | auto picks GPU when usable, else CPU | `auto` |

Model is picked by active device from `config.json`: CPU uses `model_cpu`
(default PP-OCRv6_small, 31MB), GPU uses `model_gpu` (default PP-OCRv6_medium,
136MB). `.venv` missing? Run with system `python` instead
(`python "<SKILL_DIR>/scripts/ocr.py"`) — it prints clear setup guidance.

## Setup & slash commands

The skill only needs a Python (3.8–3.13). If `.venv` or the OCR models are
missing: run `/llm-sight-status` → `python "<SKILL_DIR>/scripts/setup.py" install`
(builds `.venv` with rapidocr + onnxruntime, ~300MB; recommends downloading the
default model but doesn't force it) → `/llm-sight-status` again. No Python?
`setup.py` prints the download link — never auto-install Python yourself.

On a first model download, ask the user which model (show size + accuracy +
who it fits) and proxy (`http://127.0.0.1:<端口>`, empty = direct); then
`setup.py install --model X --proxy Y`.

| Command | Action |
|---|---|
| `/llm-sight-status` | show python / venv / models / GPU / config status |
| `/llm-sight-model` | model manager menu: download / delete / set-default (CPU/GPU) |
| `/llm-sight-config` | pick CPU/GPU model, toggle GPU, install/remove GPU module, proxy / manifest URL |
| `/llm-sight-update` | manually check for a newer OCR model |
| `/llm-sight-help` | list all commands and their uses |

On first use (config `help_hint` on, default), remind the user:
`/llm-sight-help` 可查看所有可用命令。

Config is stored in `<SKILL_DIR>/config.json` (local only; not shipped).

## GPU acceleration (optional, DirectML)

The OCR engine is onnxruntime. GPU acceleration is an optional DirectML module
(`onnxruntime-directml`) — it works on any DX12-capable GPU including NVIDIA RTX
50 series (paddle's CUDA path does NOT work on Blackwell; this skill no longer
uses paddle). On first install, if the machine has a capable GPU the setup asks
whether to enable it. **On the first OCR call, if the hardware supports DirectML,
the module is installed, and at least one model is downloaded, GPU acceleration
turns on automatically using the best downloaded model** — you can turn it off
anytime via `/llm-sight-config --gpu off`. Manage it via `/llm-sight-config`:
- `--gpu on|off` — enable/disable GPU acceleration
- `--gpu-module install|remove` — install / delete the GPU module (reinstall
  re-checks the hardware; if the machine can't use GPU it recommends NOT
  installing / deleting the module to free ~150MB)

`ocr.py` re-detects DML support on every run and records it in
`config.json` (`gpu_capable`). If it detects the module is installed but the
machine can't use it, it suggests deleting the module.

## Standard workflow

1. **Locate the image** — path (absolute/relative, expand `~`) or URL.
2. **Run the wrapper**, capture stdout:
   ```
   "<SKILL_DIR>/.venv/Scripts/python.exe" "<SKILL_DIR>/scripts/ocr.py" "<image>" --lang ch
   ```
   Add `--lang en` for English-dominant images, `--format json` for scores/positions.
   Fresh install or deps deleted (`.venv` gone)? Run `/llm-sight-status` →
   `setup.py install` to rebuild, then retry. Model deleted? `ocr.py` prints
   "模型未下载" → `/llm-sight-model` or `setup.py models add <name>`.
3. **Treat stdout as the image's text** — OCR is imperfect: `0`↔`O`, `1`↔`l`;
   low-confidence lines (in `--format json`) may be wrong. Flag anything
   implausible instead of silently trusting it.
4. **Answer with the text** — translate, summarize, quote, act. If nothing
   usable came out, say so honestly; never fabricate what the image "probably" said.

## Edge cases

- **First run is slow** — a no-bundled-models release downloads the model on the first call (minutes).
- **`(no text detected)`** — genuinely no readable text; report it, suggest a
  cleaner/straighter image.
- **Blurry/rotated text** — run anyway; PP-OCRv6 handles most photos. Heavily
  sideways → ask for a straighter image.
- **Multiple images** — pass several paths; output is separated by `# <image>`.
  If the GPU module is installed but not enabled, `ocr.py` asks whether to use
  GPU for this batch.
- **URLs** — downloaded to the skill's `tmp/` first.
- **Long documents** — OCR one image at a time; loop the command over the files.
- **Slow on CPU with the medium model** — v6 medium is GPU-oriented; on pure CPU
  it can take ~60s/image. Use the small model (`model_cpu`) for CPU, or enable GPU.

## Troubleshooting

Install, GPU, and error details live in `references/troubleshooting.md` — read it when a run fails.
