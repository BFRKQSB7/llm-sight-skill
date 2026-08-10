# llm-sight

**中文** | [English](./docs/en/README.md)

![](https://img.shields.io/badge/version-v2.0.0-blue)
![](https://img.shields.io/badge/license-MIT-green)

**给没有多模态能力的大模型一双"眼睛"**——用 PP-OCRv6 模型（rapidocr + onnxruntime，GPU 走 DirectML）把图片/截图/扫描件里的文字提取成纯文本，非多模态模型就能读取图中内容。

## 为什么用这个

你的模型（如本地部署的纯文本 LLM）看不了图片。`llm-sight` 提供一条命令：**图片 → 文字**，把 OCR 结果作为图像内容的可靠依据。模型拿到图就调它，不再瞎猜或编造图中文字。

## 特性

- **一条命令读文字**：`ocr.py <图片>` → 纯文本输出（也可 JSON 带置信度/坐标）
- **自动引导环境**：有 Python（3.8–3.13）即可——自动建 venv、装依赖、推荐下载模型；没有 Python 只提示下载链接
- **三个版本**（区别在是否自带模型 / GPU 模块）：
  - **`_lite`**：不带模型，体积最小，首次运行在线下载
  - **`_standard`**：内置 v6 small 模型（CPU 默认），开箱即用
  - **`_full`**：内置 v6 small + v6 medium（GPU 默认）+ GPU 加速模块（DirectML），开箱即用 + 可 GPU 加速
- **GPU 加速可选**：DirectML 走 D3D12，**NVIDIA RTX 50 系列（Blackwell）可用**（paddle 的 CUDA 路线在 50 系不可用，本 skill 已弃用 paddle）。首次安装检测到符合要求的显卡才提示；`/llm-sight-config` 可开/关、装/删 GPU 模块
- **CPU / GPU 各自独立模型**：CPU 默认 v6 small（快），GPU 默认 v6 medium（准），可分别配置
- **斜杠命令配置**：选模型、GPU 开关、自动更新、代理、查环境
- 模型候选（含体积/识别率/语言/适合人群）：PP-OCRv6_small / PP-OCRv6_medium / PP-OCRv6_tiny / PP-OCRv5_server / PP-OCRv4_mobile / PP-OCRv5_cyrillic（俄）/ PP-OCRv5_korean（韩）/ PP-OCRv5_arabic（阿）

## 安装

### 前提：Python（3.8–3.13，推荐 3.12）

**已经有 Python？** 跳过本节。检查：终端运行 `python --version` 或 `py -3.12 --version`。

**还没有 Python？** 建议自己装一个（llm-sight 不替你装，只会提示）：
1. 打开 https://www.python.org/downloads/ ，点最新的 **3.12.x**（Windows 选 *Windows installer (64-bit)*）
2. 安装时**务必勾选 "Add Python to PATH"**，然后 *Install Now*
3. 重开终端，`python --version` 能看到版本号即成功

### 安装 skill

1. 把 `llm-sight/` 目录放进 `~/.claude/skills/`（三个版本任选一个，按需挑）：
   - 网络好、想要最小体积 → **`_lite`**（首次识图时在线下载模型）
   - 不想下载、纯 CPU 使用 → **`_standard`**（内置 v6 small）
   - 要 GPU 加速（RTX 50 系等 DX12 显卡）→ **`_full`**（内置 small + medium + GPU 模块）
2. 首次使用前运行引导（Claude Code 里 `/llm-sight-status` 看缺什么，或直接）：
   ```bash
   python ~/.claude/skills/llm-sight/scripts/setup.py install
   ```
   - **有 Python**：自动建 venv、装依赖（~300MB）、推荐下载默认模型（不强求）
   - **无 Python**：`setup.py` 会打印官方下载链接，装好再跑一次
   - **符合要求的显卡**（可创建 D3D11 硬件设备）会询问是否启用/安装 GPU 加速
   - 任何下载都会先询问你

## 使用

```bash
python ~/.claude/skills/llm-sight/scripts/ocr.py <图片路径或URL> [--lang ch] [--format text|json]
```

`--lang` 支持：ch（默认，中英+拉丁语系）/ en / chinese_cht / japan（v6 模型）；俄文用 PP-OCRv5_cyrillic（内置）、韩文 PP-OCRv5_korean、阿拉伯 PP-OCRv5_arabic（后两者检测分框不稳，建议先试）。

在 Claude Code 里，非多模态模型遇到图片会自动触发本 skill 并调用上述命令。

## 配置（斜杠命令）

| 命令 | 作用 |
|---|---|
| `/llm-sight-status` | 查看 Python / venv / 模型 / GPU / 配置状态 |
| `/llm-sight-config` | 选 CPU/GPU 模型、GPU 开关、装/删 GPU 模块、自动更新、代理、更新清单 |
| `/llm-sight-model` | 模型管理：下载 / 删除 / 设默认（CPU/GPU 分开） |
| `/llm-sight-update` | 手动检查是否有更新的 OCR 模型 |

配置存在本机 `config.json`（不入库、不随发布分发）。

## 名字说明

`llm-sight` 意为"大模型的视力"。它封装的是 **PP-OCR**（PaddleOCR 模型经 rapidocr 转 ONNX 部署）模型，但本身不是模型、也不是 PP-OCR 本身——是一个帮非多模态大模型读取图中文字的 Claude Code skill。

## License

[MIT](./LICENSE)
