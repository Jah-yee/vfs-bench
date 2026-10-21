# 接入自定义模型

[English](CUSTOM_MODEL.md) | 中文

任何部署在 OpenAI 兼容 Chat Completions 接口后的模型，都能在两个数据集、
VFS 与 MCP 两组上运行，无需修改代码。

## 需要提供

- **接口地址**：OpenAI 兼容 API 的 base URL，例如 vLLM、SGLang、Ollama、
  LiteLLM 或 OpenRouter（`http://localhost:8000/v1`）。
- **模型 ID**：接口上提供该模型的名称。不要以 `google/`、`anthropic/` 或
  `openai/` 开头：这些前缀会切换到内置的 Gemini、Anthropic Messages 以及
  （MCP-Atlas 上的）OpenAI Responses 适配器。
- **API 密钥**：放在你自选的环境变量里，写入 `.env.development`。若服务端不校验
  密钥，任意非空值即可。
- **推理强度**：`none`、`low`、`medium`、`high`、`xhigh` 或 `max`，以
  `reasoning_effort` 字段发送；`default` 则不发送该字段。

## API 必须支持

- `POST /v1/chat/completions`，非流式。
- 工具调用：请求中的 `tools`、回复中的 `tool_calls`，以及下一次请求中
  `role: "tool"` 的结果。使用 vLLM 时，启动参数加上
  `--enable-auto-tool-choice --tool-call-parser <parser>`。
- 每个回复都带 `usage`（`prompt_tokens` 与 `completion_tokens`）：token 数正是
  基准测量的指标。
- `max_tokens` 与 `parallel_tool_calls` 字段。Toolathlon 发送
  `max_tokens: 65536` 和 `parallel_tool_calls: true`；MCP-Atlas 两者都不发送。
- 上下文窗口能容纳对话加上述生成预算。上下文用尽时，报错信息须包含
  `maximum context length`（vLLM 的报错即如此），这样运行会像上游框架一样
  清空上下文继续，而不是直接失败。
- `reasoning_effort` 字段；不支持则使用 `--reasoning-effort default` 运行。

## 运行

在 `vfs-bench-1/` 目录下，用相同参数先后运行两组：

```bash
echo 'MY_MODEL_KEY=sk-...' >> .env.development
for tools in vfs mcp; do
  uv run python agent/run_agent.py toolathlon/nhl-b2b-analysis \
    --model my-org/my-model --base-url http://localhost:8000/v1 \
    --api-key-env MY_MODEL_KEY --reasoning-effort medium --tools $tools
done
```

每次运行都会把以模型命名的记录写入 `dumps/`，并自动评分。

## 服务凭证

除模型外，任务只需为它调用的在线服务提供密钥。密钥写入 `.env.development`；
各密钥的获取方式见 `.env.example`。

| 任务 | Toolathlon | MCP-Atlas |
| --- | --: | --: |
| 完全模拟：只用本地仿真服务和固定数据 | 42 | 6 |
| 调用公开在线服务，无需密钥 | 9 | 19 |
| 至少需要一个密钥 | 49 | 75 |

模拟的服务包括 Google Workspace、Notion、GitHub、Slack、Airtable、邮件、
Snowflake、BigQuery、W&B、MongoDB 和 Hugging Face Hub。无需密钥的公开在线服务
包括浏览器、fetch、arXiv 与 Scholar、Yahoo Finance、PubMed 和 OpenStreetMap。

各密钥所需的任务数（一个任务可能需要多个）：

| 凭证 | Toolathlon | MCP-Atlas |
| --- | --: | --: |
| `E2B_API_KEY`（Canvas、WooCommerce、Kubernetes 与 E2B 沙箱） | 21 | 23 |
| `SERPER_API_KEY`（网页搜索） | 24 | |
| `EXA_API_KEY` | | 27 |
| `OXYLABS_USERNAME`、`OXYLABS_PASSWORD` | | 20 |
| `WIKIPEDIA_ACCESS_TOKEN` | | 19 |
| `WEATHER_API_KEY` | | 19 |
| `NPS_API_KEY` | | 11 |
| `GOOGLE_MAPS_API_KEY` | 6 | 5 |
| `BENCH_S3_*` 与 `AWS_*`（`k8s-mysql`、`k8s-pr-preview-testing`） | 2 | |
| `YOUTUBE_API_KEY`（`youtube-repo`） | 1 | |
| `GITHUB_TOKEN`（在线 GitHub；`git-milestone` 的评分可选） | 1 | 4 |
| `GOOGLE_APPLICATION_CREDENTIALS`（`fillout-online-forms`） | 1 | |

## MCP-Atlas 评分

Toolathlon 的评分器不调用模型。MCP-Atlas 的评分器会请一个 LLM 评委
`google/gemini-3.1-pro-preview`，使用本次运行的 `--base-url` 和密钥，
因此该接口也必须提供这个模型。自部署模型时，可在前面加一个路由：把你的模型
原样转发到你的服务，把评委转发到提供 Gemini 的网关。

## 不兼容 OpenAI？

先把模型部署在 OpenAI 兼容的服务之后。需要专有请求格式的服务商要在代码里写
适配器，就像 Toolathlon 循环中的 `agent/claude.py`、`agent/gemini.py`，以及
MCP-Atlas 的 `agent/atlas/gateway.py`；并在那里声明与上游的差异。
