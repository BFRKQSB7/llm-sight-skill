---
name: llm-sight
description: >-
  Extract text from images, screenshots, and pictures using the PaddleOCR
  models (PP-OCRv6). USE THIS whenever the user hands you an image, screenshot,
  photo, scan, or picture and expects you to read the text in it — to
  transcribe, quote, translate, summarize, or act on what the image says. This
  matters most when you are a non-multimodal model and cannot see the image
  directly: do NOT guess what the image shows, run the OCR script and read its
  output. If you try to `read` an image file and it fails, errors, or shows only
  binary/illegible content, STOP retrying `read` and use this skill instead.
  Triggers on: OCR, 识别图片文字, 图片里写了什么, 提取图片文字, 截图里的文字,
  字幕, transcribe image, read text from screenshot, what does this image say,
  convert image to text, parse text out of a picture. Also fires when the user
  pastes an image path/URL and asks any question whose answer depends on the
  image's content.
---

# llm-sight: read text out of images with PaddleOCR

You can't see the image, but you can extract its text reliably. This skill turns
an image into plain text via a thin PaddleOCR wrapper. Use the extracted text as
ground truth for whatever the user asked — never guess what the image shows.

## The one command

```bash
"<SKILL_DIR>/.venv/Scripts/python.exe" "<SKILL_DIR>/scripts/ocr.py" <image> [options]
```

`<SKILL_DIR>` = this skill's own directory (the folder containing `SKILL.md`).
Common flags:

| Flag | Meaning | Default |
|---|---|---|
| `--lang ch` | language code (ch, en, japan, korean, chinese_cht, french, german, ru, arabic…) | `ch` |
| `--format text` | text = one recognized line per stdout line | `text` |
| `--format json` | structured: texts + confidence scores + box coordinates | — |
| `--device auto` | auto picks GPU when usable, else CPU | `auto` |

The venv carries `paddlepaddle` + `paddleocr`; the model comes from
`config.json` (default PP-OCRv6_medium). Missing package (exit 2)? Run
`/llm-sight-status` then `setup.py install` once.

## Setup & slash commands

The skill only needs a Python (3.8–3.13). If `.venv` or the OCR models are
missing: run `/llm-sight-status` → `python "<SKILL_DIR>/scripts/setup.py" install`
(builds `.venv`, ~1GB, downloads the model) → `/llm-sight-status` again. No
Python? `setup.py` prints the download link — never auto-install Python yourself.

On a first model download, ask the user which model (PP-OCRv6_medium 默认 /
PP-OCRv6_tiny / PP-OCRv5_mobile / PP-OCRv5_server / PP-OCRv4_mobile) and proxy
(`http://127.0.0.1:<端口>`, empty = direct); then `setup.py install --model X --proxy Y`.

| Command | Action |
|---|---|
| `/llm-sight-status` | show python / venv / models / config status |
| `/llm-sight-model` | model manager menu: download / delete / set-default model |
| `/llm-sight-config` | pick OCR model, toggle auto-update, set proxy / manifest URL |
| `/llm-sight-update` | manually check for a newer OCR model |
| `/llm-sight-help` | list all commands and their uses |

On first use (config `help_hint` on, default), remind the user:
`/llm-sight-help` 可查看所有可用命令。

Config is stored in `<SKILL_DIR>/config.json` (local only; not shipped).

## Standard workflow

1. **Locate the image** — path (absolute/relative, expand `~`) or URL.
2. **Run the wrapper**, capture stdout:
   ```
   "<SKILL_DIR>/.venv/Scripts/python.exe" "<SKILL_DIR>/scripts/ocr.py" "<image>" --lang ch
   ```
   Add `--lang en` for English-dominant images, `--format json` for scores/positions.
   Fresh install (`.venv` missing)? A bare `ocr.py` call fails with a confusing
   "No such file or directory" — run `/llm-sight-status` → `setup.py install` first.
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
- **URLs** — downloaded to the skill's `tmp/` first.
- **Long documents** — OCR one image at a time; loop the command over the files.

## Troubleshooting

Install, GPU, and error details live in `references/troubleshooting.md` — read it when a run fails.
