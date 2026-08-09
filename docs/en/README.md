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

1. Have Python 3.8–3.13 (`py -3.12` or `python`).
2. Put the `llm-sight/` folder into `~/.claude/skills/` (pick V1 or V2).
3. Bootstrap once before first use (`/llm-sight-status` to see what's missing,
   or directly):
   ```bash
   python ~/.claude/skills/llm-sight/scripts/setup.py install
   ```
   With V2 the model-download step is skipped (models are bundled).

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
