---
description: 手动检查 llm-sight 是否有更新的 OCR 模型（/llm-sight-update）。OCR 失败、或用户怀疑模型过旧、或想看看有没有新模型时使用。
---
# llm-sight 更新检查

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" update
```

把输出读给用户。若提示有新版本，询问是否要切换：
```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" config --model <新模型名>
```
更新检查失败时不影响使用，如实告知即可。
