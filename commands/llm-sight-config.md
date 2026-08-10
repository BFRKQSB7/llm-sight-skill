---
description: 配置 llm-sight 的 OCR 模型（CPU/GPU 分开）、GPU 加速开关、GPU 模块安装/删除、自动更新、代理端口、更新清单（/llm-sight-config）。用户提到要改 llm-sight 模型、开/关 GPU、装/删 GPU 模块、开/关自动更新、配代理时使用。
---
# llm-sight 配置

运行并让用户确认：

```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" config
```

按需追加参数（逐个和用户确认）：
- CPU 默认模型：`--model-cpu <名称>`（默认 PP-OCRv6_small）
- GPU 默认模型：`--model-gpu <名称>`（默认 PP-OCRv6_medium）
- GPU 加速开关：`--gpu on|off`（on 但硬件不支持时会建议不要开/删模块）
- GPU 模块安装：`--gpu-module install`（装 onnxruntime-directml，**必弹确认提示**，先复检硬件）
- GPU 模块删除：`--gpu-module remove`（卸载并装回 CPU 版，释放 ~150MB）
- 自动更新：`--auto-update on|off`
- 代理（用于下载/更新检查，如用户网络需代理）：`--proxy http://127.0.0.1:<端口>`
- 更新清单 URL：`--manifest-url <URL>`

可用模型：PP-OCRv6_small（CPU 默认）/ PP-OCRv6_medium（GPU 默认）/ PP-OCRv6_tiny / PP-OCRv5_server / PP-OCRv4_mobile（用 `models list` 看体积/精度/适合人群）。

首次需要下载模型时：先问用户要哪个模型和是否走代理（空=直连），再跑：
```bash
py -3.12 "$HOME/.claude/skills/llm-sight/scripts/setup.py" install --model <模型名> [--proxy http://127.0.0.1:<端口>]
```

把命令输出读给用户，确认配置生效。
