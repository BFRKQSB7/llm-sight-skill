# llm-sight

**中文** | [English](./docs/en/README.md)

![](https://img.shields.io/badge/version-v1.0.1-blue)
![](https://img.shields.io/badge/license-MIT-green)

**给没有多模态能力的大模型一双"眼睛"**——用 PaddleOCR（PP-OCRv6）把图片/截图/扫描件里的文字提取成纯文本，非多模态模型就能读取图中内容。

## 为什么用这个

你的模型（如本地部署的纯文本 LLM）看不了图片。`llm-sight` 提供一条命令：**图片 → 文字**，把 OCR 结果作为图像内容的可靠依据。模型拿到图就调它，不再瞎猜或编造图中文字。

## 特性

- **一条命令读文字**：`ocr.py <图片>` → 纯文本输出（也可 JSON 带置信度/坐标）
- **自动引导环境**：有 Python（3.8–3.13）即可——自动建 venv、装依赖、下载模型；没有 Python 只提示下载链接
- **双版本交付**（唯一区别是是否自带 OCR 模型）：
  - **V1**：不带模型，体积小，首次运行在线下载（默认 PP-OCRv6_medium，约几百 MB）
  - **V2**：内置模型，拿到即用，无需下载
- **斜杠命令配置**：选模型、开/关自动更新、设代理、查环境
- **更新检查**：手动触发或 OCR 失败时自动提示，失败不影响使用
- 默认模型 PP-OCRv6_medium，可换 PP-OCRv6_tiny / PP-OCRv5_mobile / PP-OCRv5_server / PP-OCRv4_mobile

## 安装

### 前提：Python（3.8–3.13，推荐 3.12）

**已经有 Python？** 跳过本节。检查：终端运行 `python --version` 或 `py -3.12 --version`。

**还没有 Python？** 建议自己装一个（llm-sight 不替你装，只会提示）：
1. 打开 https://www.python.org/downloads/ ，点最新的 **3.12.x**（Windows 选 *Windows installer (64-bit)*）
2. 安装时**务必勾选 "Add Python to PATH"**，然后 *Install Now*
3. 重开终端，`python --version` 能看到版本号即成功

### 安装 skill

1. 把 `llm-sight/` 目录放进 `~/.claude/skills/`（V1 或 V2 任选一个）
2. 首次使用前运行引导（Claude Code 里 `/llm-sight-status` 看缺什么，或直接）：
   ```bash
   python ~/.claude/skills/llm-sight/scripts/setup.py install
   ```
   - **有 Python**：自动建 venv、装依赖、下载模型（**任何下载都会先询问你**）
   - **无 Python**：`setup.py` 会打印官方下载链接，装好再跑一次
   - **V2** 内置模型，可跳过模型下载部分

## 使用

```bash
python ~/.claude/skills/llm-sight/scripts/ocr.py <图片路径或URL> [--lang ch] [--format text|json]
```

在 Claude Code 里，非多模态模型遇到图片会自动触发本 skill 并调用上述命令。

## 配置（斜杠命令）

| 命令 | 作用 |
|---|---|
| `/llm-sight-status` | 查看 Python / venv / 模型 / 配置状态 |
| `/llm-sight-config` | 选 OCR 模型、开/关自动更新、设代理端口、设更新清单 URL |
| `/llm-sight-update` | 手动检查是否有更新的 OCR 模型 |

配置存在本机 `config.json`（不入库、不随发布分发）。

## 名字说明

`llm-sight` 意为"大模型的视力"。它封装的是 **PP-OCR**（PaddleOCR）模型，但本身不是模型、也不是 PP-OCR 本身——是一个帮非多模态大模型读取图中文字的 Claude Code skill。

## License

[MIT](./LICENSE)
