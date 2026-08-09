---
description: 查看 llm-sight 环境状态：Python/venv/OCR 模型/配置是否齐全（/llm-sight-status）。首次使用前、或 OCR 报错想排查环境时使用。
---
# llm-sight 状态检查

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" check
```

把输出读给用户，并解释缺什么、怎么补：
- Python 未找到 → 提示用户装 Python 3.8-3.13（官方下载链接在输出里）
- venv 缺失 → 运行 `setup.py install` 自动构建
- models 缺失 → 运行 `setup.py install` 下载模型
- config 缺省 → 默认用 PP-OCRv6_medium，可 `/llm-sight-config` 调整
