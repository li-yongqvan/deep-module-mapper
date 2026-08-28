# Deep Module Mapper Backend

HTTP API that wraps `parser.scan_codebase()` and exposes three endpoints for frontend polling.

## Prerequisites

- Python 3.10+
- The `parser/` sibling package must be available as an editable install.

## Install

From the repository root:

```bash
python -m pip install -e parser/ -e backend/
```

## Start the server

From the repository root:

```bash
python -m uvicorn backend.app:app --reload --port 8123
```

The server binds `127.0.0.1:8123` by default. Use `--host` and `--port` to override.

**Note**: Use `python -m uvicorn` (not bare `uvicorn`) if your system has multiple Python versions, so the command uses the interpreter that has `backend` installed.

**Note**: `--reload` restarts the process on code changes and may interrupt in-flight scans. Remove it for long-running scans.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/scan` | Start a scan. Body: `{"path": "<repo-path>"}`. Returns `202` with `{"jobId": "..."}`. |
| GET | `/api/scan/{job_id}/status` | Get job status: `pending`, `running`, `done`, or `error`. On `error`, also returns `error`/`details`. |
| GET | `/api/scan/{job_id}/graph` | Get the Graph JSON when status is `done`. Returns `409` while running/pending, `500` on error, `404` for unknown job. |

## Example curl

```bash
# Start scan
JOB=$(curl -s -X POST http://127.0.0.1:8123/api/scan \
  -H "Content-Type: application/json" \
  -d '{"path":"backend/tests/fixtures/mini_pkg"}' | python -c "import sys,json; print(json.load(sys.stdin)['jobId'])")

# Poll status until done
curl -s http://127.0.0.1:8123/api/scan/$JOB/status

# Fetch graph
curl -s http://127.0.0.1:8123/api/scan/$JOB/graph | python -m json.tool
```

## CORS

For local development, CORS defaults to `["*"]`. Set `BACKEND_CORS_ORIGINS` to a comma-separated list to restrict origins:

```bash
BACKEND_CORS_ORIGINS="http://localhost:3000,http://localhost:5173" python -m uvicorn backend.app:app --port 8123
```

## AI 聚合 CLI（issue #11）

把任意代码库聚合为功能原子 manifest（`{atoms:[{id,name,description,files}]}`，与 `frontend/src/manifest/feature-atoms.json` 同格式，drop-in 替换）。**AI 提议，人定夺**：模型读代码库的轻量 digest，判断哪些文件共同实现一个能力。

**角色分工（D1/D5，用户 2026-08-28 定）**：
- **云端 DeepSeek（OpenAI 兼容）= 唯一权威**：它的输出写入 manifest，是产品唯一事实源。
- **本地 Ollama = 学习角色**：每次运行用**本地 digest** 也产出一份自己的聚合尝试，云端成功时再用 LEARN prompt 反思「与云端答案为何不同、漏了什么」。尝试 + 云端答案 + 反思成对入训练日志。**本地答案永不写入 manifest**（best-effort，失败/不可达不影响权威路径与退出码）。

### 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_API_KEY` | **无（缺失致命）** | DeepSeek API key。缺则无法调用 API，**致命退出 1**，不进入聚合 |
| `LLM_API_BASE` | `https://api.deepseek.com/v1` | OpenAI 兼容 base URL（DeepSeek 用 `/v1`） |
| `LLM_MODEL` | `deepseek-chat` | 云端权威模型 |
| `LLM_TIMEOUT` | `60` | 云端请求超时（秒） |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | 本地 Ollama 地址 |
| `OLLAMA_MODEL` | `my-assistant` | 本地学习模型 |
| `OLLAMA_TIMEOUT` | `300` | 本地请求超时（秒）。本地 8B 模型生成完整 manifest 可能需 2-3 分钟；超时太短会拿到空响应、丢失学习记录 |

### 用法

```bash
# 从仓库根目录（editable installs 见下）自扫描聚合，写默认 manifest + 质量报告
python -m backend.backend.aggregate . --compare frontend/src/manifest/feature-atoms.json

# 只看结果不写盘（打印 manifest + 质量对拍）
python -m backend.backend.aggregate <repo> --dry-run

# 跳过本地学习（不调 Ollama、不写 sidecar）
python -m backend.backend.aggregate <repo> --skip-local

# 追加训练日志（每次运行写 role=api/local/learn 三行，同 run_id 成对）
python -m backend.backend.aggregate <repo> --training-log train.jsonl
```

可选 flags：`--output PATH`（默认 `<repo>/frontend/src/manifest/feature-atoms.json`）、`--compare PATH`（ground truth manifest，默认 = 既有 `--output` 内容即手写版）、`--report PATH`（默认 `feature-atoms.report.json` 与 manifest 同目录）。

> **前置**：需先 `python -m pip install -e parser/ -e backend/`（editable 指向本仓库）。两种调用形式都从仓库根目录跑，均依赖 cwd=仓库根。

### 失败行为（U1/U5：不回退手工）

**AI 聚合失败 → 明确报错 + 提示重试；不回退手工 manifest、不写任何 manifest。** 既有脚手架文件原样保留（非降级结果）。手写 `feature-atoms.json` 是 #8 脚手架，不是兜底。

### 退出码

| 码 | 含义 |
|---|---|
| `0` | 权威（AI）manifest 已写；有 ground truth 时报告含质量对拍 |
| `1` | 致命配置/输入错误：坏路径 / 扫描失败 / **缺 `LLM_API_KEY`** |
| `2` | AI 聚合失败（重试后仍败）→ stderr 明确「AI 聚合失败，可重试」+ 报告 `status=failed` |

### 质量对拍（U2/U4，核心交付物）

聚合质量是**客观验收指标**，不是边缘测试。对每个 ground-truth（GT）原子，在 AI 原子中找与之**文件交集最大**者（best-match，并列取先出现者，确定性）：

```
accuracy = 正确归入文件数 / GT 生产文件总数
```

- **正确归入**：GT 文件落在「其 GT 原子 ∩ 匹配 AI 原子」交集里。
- `ai_missed`：GT 有、AI 没覆盖的文件。
- `ai_extra`：AI 有、GT 没有的文件（如新增 `aggregate/*`、`__init__.py`）——**不计入 accuracy**。
- 逐原子 best-match 表 + 指标进报告（`report.quality`）与 stdout。

### 重跑

同一命令可重跑：默认 ground truth = 当前 manifest 既有内容；想换成手写版作基准就显式 `--compare frontend/src/manifest/feature-atoms.json`。

### 输出文件

- `feature-atoms.json`（drop-in manifest，权威）
- `feature-atoms.report.json`（`status: ok|failed`、`quality`、`providers`、`warnings`）
- `feature-atoms.local.json`（sidecar：本地模型输出，**权威路径永不读取**）
- `--training-log` JSONL（role=api/local/learn 三行，同 `run_id`，含**本地模型实际看到的 digest**）

### 设计

见 `wayfinder/design-doc-issue-11-ai-aggregation.md` 与 `wayfinder/grilling-decisions/issue-11-ai-aggregation-decisions.md`（D1-D14 + 评审 + U1-U6）。

## Run tests

From the repository root:

```bash
python -m pytest parser/tests backend/tests -q
```

## Design baseline

See `wayfinder/handoff-build-core-backend-api.md` and the audited design document for architecture decisions.
