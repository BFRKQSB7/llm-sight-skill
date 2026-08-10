---
description: llm-sight 交互配置面板：模型（下载/删除/设默认）+ GPU 开关/模块 + 代理 + 自动更新（/llm-sight-config）。用户想改 llm-sight 配置、装/删模型、开/关 GPU 时使用。
---
# llm-sight 配置面板（交互）

第一步，先运行看当前状态（会显示当前配置 + 已下载模型 + 可用模型）：

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" config
```

把输出读给用户。然后在**对话里给用户列出操作菜单**，等用户选（每个操作都先询问、经确认再执行）：

| 选项 | 做什么 |
|---|---|
| **[d] 下载模型** | 先 `models list` 看候选（带体积/识别率/语言），问用户要哪个 → `models add <模型名>` |
| **[r] 删除模型** | 列出已安装模型，问删哪个 → `models rm <模型名>` |
| **[s] 设默认** | 问模型 + CPU/GPU → `config --model-cpu <名>` 或 `--model-gpu <名>`（默认两者都设） |
| **[g] GPU 开关** | `config --gpu on|off`（on 但硬件不支持会提示） |
| **[u] GPU 模块** | 问装还是删 → `config --gpu-module install|remove`（装模块必弹确认、先复检硬件） |
| **[p] 代理** | 问代理地址 → `config --proxy http://127.0.0.1:<端口>` |
| **[a] 自动更新** | `config --auto-update on|off` |
| **[q] 退出** | 结束面板 |

每个操作执行后把命令输出读给用户确认。下载 / 删除 / GPU 模块等动作**任何情况下都先询问用户**，不擅自执行。

（`setup.py config` 在真实终端里跑也会直接进交互菜单；此处是对话式驱动。）
