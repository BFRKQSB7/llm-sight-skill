# llm-sight

[中文](../README.md) | **English**

![](https://img.shields.io/badge/version-v2.0.0-blue)
![](https://img.shields.io/badge/license-MIT-green)

**Give non-multimodal LLMs a pair of "eyes"** — extracts text from images,
screenshots, and scans using PP-OCRv6 models (rapidocr + onnxruntime, GPU via
DirectML), so a text-only model can read what an image says.

## Why

Your model (e.g. a local text-only LLM) cannot see images. `llm-sight` offers
one command: **image → text**, giving you reliable OCR output instead of guesses
or fabricated content.

## Features

- **One command reads text**: `ocr.py <image>` → plain text (or JSON with
  confidence scores / coordinates)
- **Auto-bootstrap**: needs only Python (3.8–3.13) — builds its own venv,
  installs deps, recommends the model download; no Python → prints the download link
- **Three release variants** (differ only in bundled models / GPU module):
  - **`_lite`**: no bundled models, smallest; downloads on first run
  - **`_standard`**: bundles the v6 small model (CPU default), works out of the box
  - **`_full`**: bundles v6 small + v6 medium (GPU default) + the GPU
    acceleration module (DirectML), out-of-the-box with GPU support
- **Optional GPU acceleration**: DirectML rides the D3D12 abstraction, so it
  works on **NVIDIA RTX 50 series (Blackwell)** — paddle's CUDA path does NOT
  work on the 50 series, and this skill no longer uses paddle. First install
  prompts only when a capable GPU is detected; `/llm-sight-config` toggles
  enable/disable and install/remove the GPU module
- **Separate models per device**: CPU defaults to v6 small (fast), GPU defaults
  to v6 medium (accurate); each configurable independently
- **Slash-command config**: pick models, GPU toggle, auto-update, proxy, status
- Model options (with size / accuracy / who-it-fits): PP-OCRv6_small /
  PP-OCRv6_medium / PP-OCRv6_tiny / PP-OCRv5_server / PP-OCRv4_mobile

## Install

### Prerequisite: Python (3.8–3.13, 3.12 recommended)

**Already have Python?** Skip this. Check with `python --version` or
`py -3.12 --version`.

**No Python yet?** Install it yourself (llm-sight won't, it only prompts):
1. Open https://www.python.org/downloads/ and click the latest **3.12.x**
   (on Windows pick *Windows installer (64-bit)*)
2. During install **check "Add Python to PATH"**, then *Install Now*
3. Open a new terminal; `python --version` showing a version means success

### Install the skill

1. Put the `llm-sight/` folder into `~/.claude/skills/` (pick one of three by
   need):
   - Good network, smallest size → **`_lite`** (downloads the model on first OCR)
   - No downloads, CPU-only → **`_standard`** (bundles v6 small)
   - GPU acceleration (RTX 50 series or any DX12 GPU) → **`_full`**
     (bundles small + medium + the GPU module)
2. Bootstrap once before first use (`/llm-sight-status` to see what's missing,
   or directly):
   ```bash
   python ~/.claude/skills/llm-sight/scripts/setup.py install
   ```
   - **With Python**: builds venv, installs deps (~300MB), recommends the
     default model download (not forced)
   - **Without Python**: `setup.py` prints the official download link;
     re-run after installing
   - **Capable GPU** (a D3D11 hardware device is creatable) → asked whether to
     enable/install GPU acceleration
   - Every download asks you first

## Usage

```bash
python ~/.claude/skills/llm-sight/scripts/ocr.py <image_path_or_url> [--lang ch] [--format text|json]
```

`--lang` supports: ch (default, Chinese + English) / en / chinese_cht / japan
(the v6 model covers these 4; other languages need a v4/v5 model).

In Claude Code, a non-multimodal model auto-triggers this skill on images and
runs the command above.

## Config (slash commands)

| Command | Action |
|---|---|
| `/llm-sight-status` | show Python / venv / models / GPU / config status |
| `/llm-sight-config` | pick CPU/GPU models, toggle GPU, install/remove the GPU module, auto-update, proxy, manifest URL |
| `/llm-sight-model` | model manager: download / delete / set-default (per CPU/GPU) |
| `/llm-sight-update` | manually check for a newer OCR model |

Config is stored in local `config.json` (not committed, not shipped).

## About the name

`llm-sight` = "sight for LLMs". It wraps the **PP-OCR** (PaddleOCR) models
(deployed as ONNX via rapidocr), but is itself a Claude Code skill that helps
non-multimodal LLMs read image text — not a model, and not PP-OCR itself.

## License

[MIT](../LICENSE)
