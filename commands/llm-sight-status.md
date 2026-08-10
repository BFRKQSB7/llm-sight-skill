---
description: 查看 llm-sight 环境状态：Python/venv/OCR 模型/GPU/配置是否齐全（/llm-sight-status）。首次使用前、或 OCR 报错想排查环境时使用。
---
# llm-sight 状态检查

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" check
```

把输出读给用户，并解释缺什么、怎么补：
- Python 未找到 → 提示用户装 Python 3.8-3.13（官方下载链接在输出里）
- venv 缺失 → 运行 `setup.py install` 自动构建（装 rapidocr + onnxruntime，~300MB）
- 模型缺失 → 运行 `setup.py install`（推荐下载默认模型）或 `/llm-sight-model`
- GPU 未启用 → 若显卡符合要求（DirectX12），可 `/llm-sight-config --gpu on`；模块未装则先 `--gpu-module install`
- config 缺省 → CPU 默认 PP-OCRv6_small、GPU 默认 PP-OCRv6_medium，可 `/llm-sight-config` 调整
