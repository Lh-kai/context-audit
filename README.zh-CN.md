# context-audit

[English](README.md) | 简体中文

**检测一次已完成的对话在指定模型上下文窗口中占用了多少 token。**

`context-audit` 接收聊天日志，用当前可用的最佳 tokenizer 统计 token，并输出使用量、
剩余空间、按角色拆分的统计和风险等级。SDK、CLI、MCP 三种形态共用同一个核心函数，
因此三者结果始终一致。

- **三种形态，一份实现**：SDK、CLI、MCP 都调用 `core.audit()`。
- **零运行时依赖**：`pip install context-audit-tool` 即可离线使用，内置中英文估算器；
  需要精确计数时再安装可选依赖。
- **优先使用真实 tokenizer**：OpenAI 使用 `tiktoken`，Qwen / DeepSeek 使用 Hugging
  Face `transformers`，加载失败自动回退。
- **日志友好**：支持消息列表、JSON、JSONL、整个目录和标准输入。
- **风险等级清晰**：`low` / `medium` / `high` / `critical`，并提供 `warning` 标记。
- **只读、本地运行**：不需要 API Key，不发起网络请求，日志不会离开本机。

> 状态：alpha。报告结构已稳定，模型注册表会持续补充。

## 安装

从 PyPI 安装（发布后）：

```bash
pip install context-audit-tool
```

> PyPI 分发包名为 `context-audit-tool`，因为 `context-audit` 已被另一个项目占用。
> Python 导入包仍是 `context_audit`，CLI 命令仍是 `context-audit`。

从源码安装：

```bash
git clone <repository-url>
cd context-audit
pip install -e .
```

可选依赖：

```bash
pip install "context-audit-tool[openai]"   # OpenAI 精确计数（tiktoken）
pip install "context-audit-tool[hf]"       # Qwen / DeepSeek tokenizer（transformers）
pip install "context-audit-tool[mcp]"      # MCP 服务入口
pip install "context-audit-tool[all]"      # 以上全部
pip install "context-audit-tool[dev]"      # pytest + ruff
pip install "context-audit-tool[release]"  # build + twine
```

需要 Python 3.10+。

## SDK 用法

```python
from context_audit import audit

messages = [
    {"role": "system", "content": "你是一个助手。"},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好，有什么可以帮你？"},
]

result = audit(messages=messages, model="qwen-max")
print(result["usage_percent"])
```

从文件或目录分析：

```python
from context_audit import audit_file, audit_dir

result = audit_file("chat.jsonl", model="qwen-max")
results = audit_dir("logs/", model="gpt-4o")

for report in results:
    print(report["file"], report["usage_percent"], report["level"])
```

手动覆盖上下文窗口：

```python
audit(messages, model="gpt-4o", context_window=64_000)
```

消息采用 OpenAI 风格结构。`content` 可以是字符串或结构化列表；存在 `name` 和
`tool_calls` 时会计入 token。支持的角色：`system`、`user`、`assistant`、`tool`
（`developer` 归入 `system`，`function` 归入 `tool`）。

## CLI 用法

```bash
context-audit analyze --file chat.jsonl --model qwen-max
context-audit analyze --dir logs/ --model gpt-4o
context-audit analyze --model gpt-4o < chat.json
context-audit analyze --file chat.jsonl --model gpt-4o --output json
context-audit analyze --file chat.jsonl --model gpt-4o --output table
```

默认输出表格：

```text
Context Audit Report
==============================================
Model           qwen-max
Context window  32,768 tokens
Used            12,456 tokens (38.0%)
Remaining       20,312 tokens
Messages        18
Risk level      LOW (warning: no)

Tokens by role
----------------------------------------------
  system           1,024
  user             5,200
  assistant        6,232
  tool                 0
  total           12,456
```

目录模式每个文件输出一行。`--output json` 输出报告：单文件或 stdin 为对象，
目录为数组，并为每项附加 `file` 字段。

退出码：`0` 成功，`1` 运行时错误（文件不存在、JSON 非法、模型不支持），
`2` CLI 参数错误。

试用示例文件：

```bash
context-audit analyze --file examples/sample_chat.jsonl --model qwen-max
```

## MCP Tool

MCP 入口暴露一个工具：`measure_context_usage`。

```bash
pip install "context-audit-tool[mcp]"
context-audit-mcp
```

客户端配置示例：

```json
{
  "mcpServers": {
    "context-audit": {
      "command": "context-audit-mcp"
    }
  }
}
```

工具参数：

| 参数             | 类型           | 必填 | 说明                   |
| ---------------- | -------------- | ---- | ---------------------- |
| `messages`       | 对象数组       | 是   | 对话消息（`role`、`content`） |
| `model`          | 字符串         | 是   | 注册表中的模型名称     |
| `context_window` | 整数           | 否   | 手动覆盖上下文窗口     |

返回值与 SDK、CLI 完全相同的报告字典。

## 支持的模型

| 模型                | 提供商    | 上下文窗口 | Token 计算方式              |
| ------------------- | --------- | ---------: | --------------------------- |
| `gpt-4o`            | OpenAI    |    128,000 | `tiktoken`（`o200k_base`）  |
| `gpt-4o-mini`       | OpenAI    |    128,000 | `tiktoken`（`o200k_base`）  |
| `gpt-4-turbo`       | OpenAI    |    128,000 | `tiktoken`（`cl100k_base`） |
| `gpt-4`             | OpenAI    |      8,192 | `tiktoken`（`cl100k_base`） |
| `gpt-3.5-turbo`     | OpenAI    |     16,385 | `tiktoken`（`cl100k_base`） |
| `claude-3-5-sonnet` | Anthropic |    200,000 | 估算器                      |
| `claude-3-7-sonnet` | Anthropic |    200,000 | 估算器                      |
| `claude-3-haiku`    | Anthropic |    200,000 | 估算器                      |
| `claude-3-opus`     | Anthropic |    200,000 | 估算器                      |
| `qwen-max`          | Qwen      |     32,768 | Hugging Face tokenizer      |
| `qwen-plus`         | Qwen      |    131,072 | Hugging Face tokenizer      |
| `qwen-turbo`        | Qwen      |      8,192 | Hugging Face tokenizer      |
| `qwen-long`         | Qwen      | 10,000,000 | Hugging Face tokenizer      |
| `deepseek-chat`     | DeepSeek  |    128,000 | Hugging Face tokenizer      |
| `deepseek-reasoner` | DeepSeek  |    128,000 | Hugging Face tokenizer      |

带版本号的名字（如 `gpt-4o-2024-08-06`）会解析到基础模型，报告中保留原始名称。
窗口大小是注册表默认值，可用 `context_window` 覆盖。新增模型请修改
[`src/context_audit/models.py`](src/context_audit/models.py)。

## Token 计算说明

1. **OpenAI**：使用 `tiktoken`，按模型配置的编码计算。
2. **Qwen / DeepSeek**：使用对应的 Hugging Face tokenizer（不启用远程代码执行）。
3. **回退估算**：CJK 字符按 1 token/字，其他文本约 4 字符/token。

可选依赖缺失、tokenizer 无法加载（如离线且无缓存）或手动强制时使用估算：

```bash
export CONTEXT_AUDIT_TOKENIZER=estimate
```

统计范围包括消息的 `content`、`name` 和序列化后的 `tool_calls`，不包含聊天模板
的框架开销，因此与实际计费 token 可能略有差异。需要精确值时请安装对应 tokenizer
可选依赖。

## 报告结构

```json
{
  "model": "qwen-max",
  "context_window": 32768,
  "total_tokens": 12456,
  "usage_ratio": 0.38,
  "usage_percent": "38.0%",
  "remaining_tokens": 20312,
  "breakdown": {
    "system_tokens": 1024,
    "user_tokens": 5200,
    "assistant_tokens": 6232,
    "tool_tokens": 0
  },
  "message_count": 18,
  "level": "low",
  "warning": false
}
```

风险等级：

| 等级       | 使用率            | `warning` |
| ---------- | ----------------- | --------- |
| `low`      | `< 60%`           | `false`   |
| `medium`   | `60%` – `< 80%`   | `false`   |
| `high`     | `80%` – `< 95%`   | `true`    |
| `critical` | `>= 95%`          | `true`    |

`remaining_tokens` 不会小于 0；对话已超出窗口时使用率可超过 100%。

## 开发

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 发布到 PyPI

```bash
pip install ".[release]"
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

发布前请同步修改 `pyproject.toml` 与 `src/context_audit/__init__.py` 中的版本号。

## 安全

工具只读、本地运行；安全策略与数据处理说明见 [SECURITY.md](SECURITY.md)。

## 许可证

[MIT](LICENSE) © context-audit contributors
