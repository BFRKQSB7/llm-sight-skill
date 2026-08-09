# llm-sight

[中文](../README.md) | **English**

![](https://img.shields.io/badge/version-v1.0.1-blue)
![](https://img.shields.io/badge/license-MIT-green)

**Give non-multimodal LLMs a pair of "eyes"** — extracts text from images,
screenshots, and scans using PaddleOCR (PP-OCRv6), so a text-only model can read
what an image says.

## Why

Your model (e.g. a local text-only LLM) cannot see images. `llm-sight` offers
one command: **image → text**, giving you reliable OCR output instead of guesses
or fabricated content.

## Features

- **One command reads text**: `ocr.py <image>` → plain text (or JSON with
  confidence scores / coordinates)
- **Auto-bootstrap**: needs only Python (3.8–3.13) — builds its own venv,
  installs deps, downloads the model; no Python → prints the download link
- **Two release variants** (the ONLY difference is bundled OCR models):
  - **V1**: no bundled models, small; downloads on first run (default
    PP-OCRv6_medium, ~hundreds of MB)
  - **V2**: models bundled, works out of the box, no download
- **Slash-command config**: pick OCR model, toggle auto-update, set proxy,
  inspect environment
- **Update check**: manual or auto-triggered on OCR failure; non-blocking
- Default model PP-OCRv6_medium; also PP-OCRv6_tiny / PP-OCRv5_mobile /
  PP-OCRv5_server / PP-OCRv4_mobile

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

1. Put the `llm-sight/` folder into `~/.claude/skills/` (pick V1 or V2).
2. Bootstrap once before first use (`/llm-sight-status` to see what's missing,
   or directly):
   ```bash
   python ~/.claude/skills/llm-sight/scripts/setup.py install
   ```
   - **With Python**: builds venv, installs deps, downloads the model (**every
     download asks you first**)
   - **Without Python**: `setup.py` prints the official download link;
     re-run after installing
   - **V2**: models bundled — the model-download step is skipped

## Usage

```bash
python ~/.claude/skills/llm-sight/scripts/ocr.py <image_path_or_url> [--lang ch] [--format text|json]
```

In Claude Code, a non-multimodal model auto-triggers this skill on images and
runs the command above.

## Config (slash commands)

| Command | Action |
|---|---|
| `/llm-sight-status` | show Python / venv / models / config status |
| `/llm-sight-config` | pick OCR model, toggle auto-update, set proxy port, set manifest URL |
| `/llm-sight-update` | manually check for a newer OCR model |

Config is stored in local `config.json` (not committed, not shipped).

## About the name

`llm-sight` = "sight for LLMs". It wraps the **PP-OCR** (PaddleOCR) models, but
is itself a Claude Code skill that helps non-multimodal LLMs read image text —
not a model, and not PP-OCR itself.

## License

[MIT](../LICENSE)
