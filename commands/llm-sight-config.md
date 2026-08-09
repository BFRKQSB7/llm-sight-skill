---
description: 配置 llm-sight 的 OCR 模型、自动更新开关、代理端口、更新清单（/llm-sight-config）。用户提到要改 llm-sight 模型、开/关自动更新、配代理时使用。
---
# llm-sight 配置

运行配置命令并让用户确认：

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" config
```

按需追加参数（逐个和用户确认）：
- 改模型：`--model <名称>`，可用：`PP-OCRv6_medium`（默认）/ `PP-OCRv6_tiny` / `PP-OCRv5_mobile` / `PP-OCRv5_server` / `PP-OCRv4_mobile`
- 自动更新：`--auto-update on|off`
- 代理（用于更新检查，如用户网络需代理）：`--proxy http://127.0.0.1:<端口>`
- 更新清单 URL：`--manifest-url <URL>`

把命令输出读给用户，确认配置生效。
