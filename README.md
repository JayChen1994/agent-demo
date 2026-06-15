# agent-demo · 可配置 Agent 流水线编排引擎

最小化演示两件事：
1. **流程化配置/编排** —— 声明式 DAG：业务自由增减/开关/重排处理步骤，引擎按 IO 契约自动推导依赖与并行；
2. **Agent 能力改造** —— `AgentStep` 用 **LangGraph StateGraph** 实现 critic 回环（draft → critique → revise），把单次 LLM 升级为会自检的多轮 Agent。

**真实能力，零耦合**：LLM（真实 Gemini）与生图（真实 portrait_gen 网关）均在本项目内自包含实现
（`app/services/llm_client.py`、`app/services/image_client.py`），不依赖 `` 任何代码。

技术方案见 [`docs/技术方案-可配置Agent流水线编排.md`](docs/技术方案-可配置Agent流水线编排.md)，
架构图见 [`docs/assets/agent-pipeline-arch.drawio`](docs/assets/agent-pipeline-arch.drawio)。

## 快速开始

```bash
docker compose up -d        # MySQL + Redis
# .env 配置真实凭据：GOOGLE_API_KEYS / GEMINI_BACKEND / LLM_MODEL /
#                    PORTRAIT_GEN_BASE_URL / PORTRAIT_GEN_PROVIDER / ...
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8010
```

打开 http://127.0.0.1:8010/ ，左侧开关步骤即改流程，点击「▶ 执行流水线」看实时执行、Agent 自检过程与**真实生成的关键帧画廊**。

无头 CLI（复用同一引擎，便于验证）：

```bash
.venv/bin/python scripts/run_agent_pipeline_demo.py              # 全链路（含真实生图）
.venv/bin/python scripts/run_agent_pipeline_demo.py --no-image   # 仅 LLM 链路，更快
```

> 步骤内 LLM/生图均为**真实调用**，需在 `.env` 配置有效凭据。

## 目录

- `app/engine/` 编排引擎内核（registry / context / agent · LangGraph / executor / prompts / steps）
- `app/services/llm_client.py` 真实 Gemini 客户端（多 key 轮询 · 结构化 JSON · 自包含）
- `app/services/image_client.py` 真实 portrait_gen 生图客户端（提交+轮询 · 信号量限流 · 自包含）
- `app/services/pipeline.py` 模板 CRUD + 运行调度 + SSE 广播
- `app/api/v1/endpoints/pipeline.py` 接口层（含 SSE）
- `app/static/index.html` 单页前端（编排配置 + 实时执行 + 关键帧画廊）
- `scripts/run_agent_pipeline_demo.py` 无头 CLI 全链路运行器
