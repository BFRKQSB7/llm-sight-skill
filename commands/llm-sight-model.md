---
description: llm-sight 模型管理菜单：下载/删除/设默认 OCR 模型（/llm-sight-model）。用户想换模型、删模型、看装了哪些模型时使用。
---
# llm-sight 模型管理

运行交互菜单（或直接列清单）：

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" models menu
```

非交互环境会打印列表；也可直接指定：
- 列出（含体积/识别率/语言/适合人群）：`... models list`
- 设默认（CPU+GPU 一起）：`... models set-default <模型名>`
- 仅设 CPU 默认：`... models set-default <模型名> --cpu`
- 仅设 GPU 默认：`... models set-default <模型名> --gpu`
- 下载：`... models add <模型名> [--proxy http://127.0.0.1:<端口>]`
- 删除：`... models rm <模型名>`

把结果读给用户确认。模型名可选：PP-OCRv6_small（CPU 默认）/ PP-OCRv6_medium（GPU 默认）/ PP-OCRv6_tiny / PP-OCRv5_server / PP-OCRv4_mobile。
