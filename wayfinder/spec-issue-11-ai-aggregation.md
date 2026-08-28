# Issue #11 AI 聚合 — 8-spec 规划书（聪明区分解）

> 关联文档：设计文档 `wayfinder/design-doc-issue-11-ai-aggregation.md`；决策归档 `wayfinder/grilling-decisions/issue-11-ai-aggregation-decisions.md`。
> 定稿：2026-08-28（用户确认方法后定稿）。每个 spec = 一次专注会话 = 一个 PR（引用 issue #11）；不建新 issue（落地决策）。

## 一句话

用 AI 聚合替代手写 `feature-atoms.json`：**云端 DeepSeek 独任**（唯一权威 manifest）；**本地 Ollama = 学习角色**（产出自己答案 + 对比云端反思，只进训练日志）；**失败 = 明确报错 + 提示重试，不回退手工**。

## 切分原则

一个 spec = 一次专注会话 = 一个 PR = 一个清晰测试 seam = 独立可验证。串行依赖但每步可交付；避免把全部耦合决策塞进一个计划（愚蠢区 → 质量崩）。

## Seam 策略（全局只追求一个最高 seam）

- **最高 seam**：`run_aggregation(repo_path, config, providers, ...)` —— 注入 fake providers，测完整流程（happy/repair/failure/compare/local-learning/report/exit code）。
- **provider 传输 seam**：`_http.post_json`（monkeypatch）—— 测传输层重试/超时/HTTP 错误，不联网。
- **纯函数 seam**：`digest`/`validate`/`compare`/`prompt` 直接单测（确定性、可复现）。

## 8-spec 总览

| # | spec | seam | 依赖 |
|---|---|---|---|
| S1 | 骨架：CLI+config+_http+失败语义 | `run_aggregation` 骨架 + `post_json` | 环境前置 |
| S2 | Provider（DeepSeek+Ollama）+retry/repair | `post_json` | S1 |
| S3 | 轻量 digest + prompt | 纯函数 | S1 |
| S4 | 校验 + 质量对拍 | 纯函数 | 可并行 |
| S5 | 编排 runner + 报告（云端权威） | `run_aggregation`（最高） | S1-S4 |
| S6 | 本地学习流程 | S5 seam 扩展 | S5 |
| S7 | 前端 Policy A + fixture + AI manifest | npm test/tsc | S5 |
| S8 | 文档 + 真实端到端验收 + 落档 | 验收 | S5/S6 |

## 红线

不改 parser 公共 API / 不动 `/api/scan*` / 不改 manifest 契约（drop-in only）/ 不做画布评审端点 / **不建 issue** / 前端生产代码零改动 / 敏感操作逐项授权。

## 退出码语义（全局约定）

- `0` — 权威（AI）manifest 已写，含质量对拍（有 GT 时）。
- `1` — 致命：坏路径 / 扫描失败 / 缺 `LLM_API_KEY`（配置/输入错误，不降级）。
- `2` — AI 聚合失败（重试后仍败）→ **明确报错 + 「AI 聚合失败，可重试」**；不写任何 manifest；报告 status=failed。

---

## S1 — 基础设施骨架（配置 / 传输 / CLI 失败语义）

**Problem Statement**：从零起一个可跑的聚合 CLI；缺 `LLM_API_KEY`、坏路径时能明确失败——不静默、不回退手工（U1/U5）。

**Solution**：`backend/backend/aggregate/` 包；`config.py`（env-only）；`_http.py`（urllib+ProxyHandler+类型化错误）；`__main__.py`（argparse：`--output/--dry-run/--report/--skip-local`）；`run_aggregation` 骨架（路径校验 + 缺 key 判定 + 失败文案 + provider 注入点预留）。

**User Stories**：
1. As 开发者, I want 一条可跑的 CLI 入口, so that 聚合可被调用。
2. As 开发者, I want 缺配置/坏路径时明确报错 + 退出码区分, so that 失败不静默、可重试。
3. As 脚本调用方, I want 退出码 0/1/2 语义稳定, so that CI 能据此决策。

**Implementation Decisions**：env-only 配置（LLM_API_BASE/KEY/MODEL、OLLAMA_HOST/MODEL、超时）；退出码 0=成功 / 1=配置或输入致命 / 2=AI 失败可重试；失败 stderr 含「AI 聚合失败，可重试」；`run_aggregation(repo_path, config, *, api_provider, local_provider)` 注入签名。

**Testing Decisions**：seam = `run_aggregation` 骨架（坏路径→1、缺 key→1、stderr 文案）+ `post_json`（超时/HTTPError/代理）。只测外部行为（退出码、stderr），不测内部。先例：`parser/__main__.py` CLI + 后端 TestClient。

**Out of Scope**：真实 provider、digest、prompt、写 manifest、本地学习。

**依赖**：环境前置（worktree + editable re-point）。**Done when**：缺 key/坏路径跑出退出 1 + 明确文案；`run_aggregation` 签名可注入 provider。

---

## S2 — Provider 抽象 + 重试/修复（DeepSeek + Ollama）

**Problem Statement**：后端零 AI 代码，需建可换 provider；本地模型指令弱，需 retry/repair 才能拿到合法输出。

**Solution**：`providers.py`：`Provider` Protocol + `ProviderResult` + `OpenAICompatProvider`（DeepSeek）+ `OllamaProvider` + `retry_with_repair` + `get_provider()`。

**User Stories**：
1. As 开发者, I want provider 可注入可换, so that 换模型/换服务是单点改动。
2. As 用户, I want 传输失败自动重试 + 畸形输出 repair, so that 弱模型也能稳定出合法结果。

**Implementation Decisions**：传输重试「总尝试 3 次（1+2，退避 1s,2s）」，4xx 不重试；repair 单次；DeepSeek 取 `choices[0].message.content`；Ollama 取 `message.content`。

**Testing Decisions**：seam = `post_json` monkeypatch。fake transport：5xx 重试/超时/4xx 不重试/响应解析/repair 流程。先例：后端 TestClient 模式（新 seam 但同构）。

**Out of Scope**：编排、digest/prompt 内容。**依赖**：S1。

---

## S3 — 轻量 digest + prompt 工程

**Problem Statement**：qwen3:8b 上下文有限，喂什么、怎么问才能让弱模型稳定输出合法 JSON。

**Solution**：`digest.py`（路径 + imports[edges 提取] + 端口，确定性截断阶梯）；`prompt.py`（SYSTEM/USER/REPAIR/LEARN，`{{DIGEST}}` 占位符）。

**User Stories**：
1. As 用户, I want 输入轻量且预算可控, so that 大项目也能跑。
2. As 用户, I want prompt 强结构 + few-shot + repair, so that 弱模型也尽量出合法 JSON。

**Implementation Decisions**：digest = 路径+imports+端口（kind/name/signature/params/docstring），**无全文 excerpt**；截断阶梯 docstring→params→端口细节，永不丢 id/imports；本地 12K / API 40K；LEARN prompt 宽松格式（学习材料非产品工件）。

**Testing Decisions**：纯函数单测：digest 确定性/滤噪声/imports 提取/阶梯/缺文件不崩；prompt 渲染（占位符替换）。先例：parser 单测。

**Out of Scope**：provider 调用、写文件。**依赖**：S1（预算值）。

---

## S4 — 校验 + 质量对拍

**Problem Statement**：输出必须合法（drop-in），且质量可量化（U2/U4 核心交付物，非边缘测试）。

**Solution**：`validate.py`（pydantic `extra="forbid"` + 6 规则）；`compare.py`（best-match accuracy/missed/extra/逐原子表）。

**User Stories**：
1. As 用户, I want 每个结果有客观质量分 vs 手写 manifest, so that 不看代码也能判断 AI 分组准不准。
2. As 前端, I want 输出形状严格 drop-in, so that 消费契约不破。

**Implementation Decisions**：validate 6 规则（id 唯一/字段非空/无跨原子/真实 module id/禁噪声/C2 覆盖）；compare best-match 定义——GT 原子 ↔ AI 原子交集最大匹配，accuracy=正确归入/GT 生产文件。

**Testing Decisions**：纯函数单测。已知 GT+AI → 精确 accuracy/missed/extra；校验规则逐条（缺覆盖/噪声/编造路径/跨原子/id 重复/空字段/extra=forbid）。

**Out of Scope**：编排。**依赖**：无（可与 S2/S3 并行）。

---

## S5 — 编排 runner（云端权威流程 + 报告）

**Problem Statement**：串起 scan→digest→providers→validate→compare→write→report 全链路；云端唯一权威；失败明确报错、不回退手工（U1）。

**Solution**：`runner.py` 完整流程 + `report.py`（status=ok/failed + quality + providers + warnings）。

**User Stories**：
1. As 用户, I want 一条命令产出 drop-in 权威 manifest + 质量报告, so that 聚合可复现、可验收。
2. As 用户, I want AI 失败时明确报错 + 提示重试、不回退手工, so that 不把脚手架当结果。

**Implementation Decisions**：决策树——API ok+校验→compare→写→退出 0；API 失败→明确报错→退出 2；**不回退手工、不写任何 manifest**。report 含 quality 字段。写盘前 `parent.mkdir`。

**Testing Decisions**：**最高 seam** `run_aggregation`（注入 fake providers）：happy（写文件+quality+退出 0）/ repair / failure（不写任何 manifest、脚手架未动、退出 2、stderr 含可重试）。先例：后端 TestClient + 轮询模式。

**Out of Scope**：本地学习、前端、文档。**依赖**：S1-S4。

---

## S6 — 本地学习流程（对比学习）

**Problem Statement**：本地模型 = 学习角色，聚合完全交云端（U6）；本地要产出「自己答案 + 与云端差异反思」供训练。

**Solution**：本地 attempt（本地 digest 出自己答案）→ 云端成功时 LEARN prompt 反思 → sidecar（`feature-atoms.local.json`）+ `--training-log`（role=api/local/learn 三行，成对采集）。

**User Stories**：
1. As 用户, I want 本地模型每次运行产出自己答案 + 与云端差异的反思, so that 我能用它训练本地模型。
2. As 用户, I want 本地失败不影响权威结果, so that 学习是 bonus 不是负担。

**Implementation Decisions**：本地 attempt 用**本地 digest**；云端成功时才跑 LEARN 反思；jsonl 三行同 run_id 成对；本地答案**永不写权威 manifest**。

**Testing Decisions**：S5 seam 扩展：本地失败不致命（manifest 仍来自 API、退出 0）；LEARN 反思入日志（role=learn）；云端失败不跑反思；`--skip-local`；jsonl 追加不覆盖。

**Out of Scope**：云端权威路径。**依赖**：S5。

---

## S7 — 前端 Policy A（测试分组无关 + fixture + AI manifest 提交）

**Problem Statement**：AI 分组变化会挂前端硬编码测试（featureAtoms.test.ts / graphToFeatureFlow.test.ts）；需让功能视图测试不再钉死具体分组。

**Solution**：改 2 个测试断言动态化；parser CLI 重生成 fixture；自扫描跑 S5 提交 AI manifest；**三方同 commit 同绿**。

**User Stories**：
1. As 前端开发者, I want 功能视图测试不钉死具体分组, so that AI 提议自由分组不破坏 CI。
2. As 用户, I want 自扫描 manifest 反映真实 AI 分组, so that 功能视图可信（drop-in）。

**Implementation Decisions**：`graphToFeatureFlow.test.ts` 从 `FEATURE_ATOMS`/`atomForFile` 动态推导；`featureAtoms.test.ts` 删具体 id 断言、保 C2；`unassignedCount` 动态化；`Inspector.test.tsx` 不动。

**Testing Decisions**：`npm test` 全绿 + `npx tsc --noEmit`；C2 覆盖断言保持。先例：现有 vitest 模式。

**Out of Scope**：前端生产代码（`featureAtoms.ts`/transform/消费者/`App.tsx`）。**依赖**：S5（产出 manifest）。

---

## S8 — 文档 + 真实端到端验收 + 决策落档

**Problem Statement**：交付收尾、验收可复核；聚合质量对比必须进汇报（U2/U4）。

**Solution**：README（backend/frontend）+ 真实 DeepSeek 端到端（六步，含对拍数据）+ grilling-decisions 落档 + PR description 引用偏离登记。

**User Stories**：
1. As 维护者, I want 文档 + 真实对拍数据 + 决策落档, so that 验收可复核、后续会话可接续。
2. As 用户, I want 汇报含聚合 vs 手写对拍 accuracy, so that 知道这版聚合有多准。

**Implementation Decisions**：README 记录 config/用法/**失败行为（不回退手工）**/对拍解读/重跑；PR 引用偏离登记 + D1/D5/D9 原话。

**Testing Decisions**：真实端到端 6 步：全绿 → 自扫描聚合 → 本地学习采集 → 失败演示 → **对拍 accuracy 进最终汇报**。

**依赖**：S5/S6（S7 可并入）。

## 落地决策（用户确认 2026-08-28）

- **不建任何新 GitHub issue**（避免碎片化跟踪、打破 map.md 前沿结构）。
- 每个 spec 一个 PR，均**引用 issue #11**；一次会话只做一个 spec（one-ticket-per-session）。
- 设计文档与 grilling-decisions 落档同批写入仓库。
