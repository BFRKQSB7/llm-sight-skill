---
description: llm-sight 帮助：列出所有可用命令及用途（/llm-sight-help）。用户想知道 llm-sight 有哪些命令、或模型不确定该用哪个命令时使用。
---
# llm-sight 帮助

llm-sight 是给非多模态大模型读图中文字的 skill（PP-OCRv6 模型 / rapidocr + onnxruntime 封装，GPU 走 DirectML）。可用命令：

| 命令 | 用途 |
|---|---|
| `/llm-sight-status` | 查看 Python / venv / 模型 / GPU / 配置是否齐全 |
| `/llm-sight-model` | 模型管理菜单：下载 / 删除 / 设默认（CPU/GPU 分开） |
| `/llm-sight-config` | 交互配置面板：模型（下载/删除/设默认）、GPU 开关/模块、自动更新、代理 |
| `/llm-sight-update` | 手动检查是否有更新的 OCR 模型 |
| `/llm-sight-help` | 本帮助 |

首次使用：`/llm-sight-status` 看缺什么 → `/llm-sight-model`（或 `setup.py install`）下载模型，**任何下载都会先询问你**。
