# 可审计设计文档 — issue #11 AI 聚合（DeepSeek 主力 + Ollama 训练采集 + CLI）v2

> 文档用途：交付专业评审 agent 的评审对象。范围 = 背景 / 真值核对 / 决策记录 / 实现方案 / 不变量 / 验证。
> 溯源约定：**事实**标来源（代码 `file:line` / 命令输出摘录 / GitHub issue / 用户确认）；**判断性裁决**单独标注【决策】并给出理由与备选，不冒充事实。
> 数据时点：2026-08-28（真值核对执行日；v2 = 评审 F1-F13 落地 + 用户补充 U1-U6 并入）。
> 评审状态：评审有条件通过（2026-08-28，见 §10）；用户补充 U1-U6 并入 v2；**2026-08-28 用户确认设计定稿**。
> 关联文档：8-spec 规划书 `wayfinder/spec-issue-11-ai-aggregation.md`；决策归档 `wayfinder/grilling-decisions/issue-11-ai-aggregation-decisions.md`。

---

## §0 项目上下文（给零背景评审 agent 先读本节）

**这是什么**：Deep Module Mapper（deep-module-mapper）是一个「代码库模块地图」本地 Web 工具——给定任意代码库，解析出模块/端口/依赖并可视化，支持功能原子视图与重组画布。本票（GitHub issue #11）把**手工维护的功能原子 manifest** 替换为 **AI 聚合**：模型读文件内容，判断哪些文件共同实现一个能力，产出功能原子清单。**AI 提议，人定夺**。

**技术栈与目录**：
- `parser/` — Python AST 解析器包（`deep_module_mapper_parser`），公共 API 仅 `scan_codebase(root) -> dict`（红线：不改）。
- `backend/` — Starlette 后端包（`backend/backend/`：`app.py` 三个端点 scan/status/graph、`models.py`、`scanner.py`、`store.py`）。依赖 starlette/uvicorn/pydantic/parser。
- `frontend/` — Vite + React 19 + `@xyflow/react`。`src/manifest/featureAtoms.ts` 静态 import `feature-atoms.json`。

**关键架构纪律**：manifest 契约 = `{ atoms: [{ id, name, description, files }] }`（drop-in，不可改）；后端无任何 AI 代码（需新建 provider 抽象）；scan Graph 不含文件内容（聚合需自行从磁盘重读）；后端配置走 env-only 惯例（`BACKEND_CORS_ORIGINS` 先例）。

**角色与权限**：执行 Agent（Worker）只实现本票并汇报，不更新 `wayfinder/map.md`、不开/改/关 issue、不合并/关 PR/删分支/push main。敏感操作需逐项授权。

**前序工作**：#8 功能视图 + 手写 manifest（已完成）→ #10 重组层（已完成）→ #11 AI 聚合（本票）。handoff 见 `wayfinder/handoff-ai-aggregation.md`。

**术语速查**（`UBIQUITOUS_LANGUAGE.md`）：**功能原子** = 功能视图里最小的人可见单位，代表一组相关文件，图上表现为一个节点；重组时最小拖拽单元。**本地模型** = 运行在本地（Ollama）的轻量模型。**云端模型** = 通过 API 调用的远程大模型。

---

## §1 背景与目标

**需求来源**：GitHub issue #11（https://github.com/li-yongqvan/deep-module-mapper/issues/11，2026-08-26 创建）；交接依据 `wayfinder/handoff-ai-aggregation.md`（500ad5b 提交，issue #11 handoff）。

**目标**：用 AI 聚合替代手工维护的 `frontend/src/manifest/feature-atoms.json`，输出是同一 `FeatureAtom` 形状的 **drop-in 替换**。北极星：**AI 提议，人定夺**——AI 给出分组提议，人工最终裁决。

**用户补充要求（2026-08-28，任务说明原话）**：「我使用本地模型，更多的目的是出于训练我的本地模型，而不是让它承担相应的任务。所以我希望主要的职责还是由使用API接口的大模型来完成。」→ **本地模型只做训练采集，主力 = API 大模型。**

**用户补充要求（2026-08-28，U1-U6，覆盖/收紧验收口径）**：
- **U1（纯 AI）**：聚合层 = 纯 AI 判断，不加人工纠错；**AI 聚合失败 → 明确报错 + 提示重试，不回退手工 manifest**（手写 `feature-atoms.json` 是 #8 临时脚手架，非最终形态、非兜底）。→ **覆盖 issue #11 验收「回退手工 manifest」条款**。
- **U2/U4（质量可验证）**：本地模型指令纪律弱，聚合易分错/漏文件；须用**客观基准验收**——deep-module-mapper 自己的手写 manifest 是现成 ground truth，AI 结果与其对拍，报「能正确归入对应功能原子的文件占比」。**聚合质量对比 = 核心交付物，不是边缘测试**。
- **U3（喂什么）**：qwen3:8b 上下文有限，需明确决策「喂什么」；建议**先做轻量**（端口签名 + docstring + imports + 文件路径），标注选择、理由、失效项目规模。
- **U5（降级呈现）**：模型挂了 → 明确告诉用户「AI 聚合失败，可重试」，不静默。
- **U6（本地模型=学习角色，2026-08-28 第二段）**：**聚合完全交云端**（本地负责聚合不靠谱）；本地模型的角色是**学习**——它也产出自己的答案，然后**对比云端答案，反思「为何不同、漏了什么」，从中学习**。其答案永不用于产品（非权威、非兜底）。

**验收标准（issue #11 body，U1 修正后）**：AI 聚合路径（给定扫描 Graph + 文件内容）→ 产出功能原子 manifest；格式与手写版 drop-in 一致；**新建** AI provider 抽象（可换 provider）；prompt 精工且文档化（强结构 + JSON + few-shot）；**失败 = 明确报错 + 提示重试（不回退手写）**；测试（mock 模型、畸形处理、失败路径）；**质量对拍（vs 手写 manifest）进验证报告**；README 记录模型配置与重跑方式。

---

## §2 真值核对（数据来源，全部可复现）

### 2.1 代码真值 — manifest 契约与加载方式

| # | 声明 | 证据（命令/读取 + 结果摘录） | 结论 |
|---|---|---|---|
| T1 | manifest 契约 = `{ atoms: [{id,name,description,files}] }` | 读 `frontend/src/manifest/featureAtoms.ts:12-21`：`interface FeatureAtom { id; name; // Chinese name; description; files: string[] }`；`interface FeatureAtomManifest { atoms: FeatureAtom[] }` | ✅ 属实 |
| T2 | `featureAtoms.ts` 静态 import JSON | `featureAtoms.ts:10`：`import featureAtomsJson from './feature-atoms.json';`；`featureAtoms.ts:24-26` 从 `.atoms` 派生 `FEATURE_ATOMS` | ✅ 属实（构建期编译进 bundle，无运行时加载） |
| T3 | 现 manifest 恰 2 个原子 | 读 `frontend/src/manifest/feature-atoms.json`：`scan-and-parse`（8 parser 文件）+ `scan-api`（4 backend 文件） | ✅ 属实 |
| T4 | 消费者 | `graphToFeatureFlow.ts`、`recompose/derive.ts`、`recompose/edges.ts` import `atomForFile`（探索代理 grep 确认；`featureAtoms.ts:36` 导出 `atomForFile`） | ✅ 属实 |
| T5 | 后端无任何 AI 代码 / 无 HTTP client 依赖 | `grep -rin "ollama|openai|anthropic|httpx|requests\\.|urllib" backend/backend/` → **空结果** | ✅ 属实（需新建 provider 抽象） |
| T6 | 后端恰 3 端点 | 读 `backend/backend/app.py:106-110`：`routes = [POST /api/scan, GET /api/scan/{job_id}/status, GET /api/scan/{job_id}/graph]` | ✅ 属实 |
| T7 | scan Graph 不含文件内容 | 探索代理读 `parser/_scanner.py`（解析后内容丢弃）+ Graph 仅 5 键。实测 fixture Graph 键：`python -c` 输出 `graph keys: ['modules','ports','edges','externalModules','diagnostics']`；模块字段仅 `{id,path,ports}` | ✅ 属实（聚合需自行读磁盘 / 提取 imports） |
| T8 | parser 公共 API = `scan_codebase` | `parser/__main__.py:12-13`：`from . import scan_codebase`；`scan_codebase(args.repo_path)` | ✅ 属实 |
| T9 | CLI 先例：argparse + `--output`，`json.dumps(indent=2, ensure_ascii=False)` | `parser/__main__.py:16-30` | ✅ 属实 |
| T10 | 后端测试入口用 `from backend.app import app` | `backend/tests/conftest.py`（探索代理核实） | ✅ 属实 |
| T16 | graph edges 含 import/from_import 种类，可据此提取「每模块 imports」 | `parser/_schema.py`（探索代理）：`Edge {source, target, kind ∈ import|from_import|call|inheritance|annotation|decorator, sites}` | ✅ 属实（digest 轻量方案的 imports 来源，U3） |

### 2.2 代码真值 — 前端测试硬编码（Policy A 决策依据，最高风险点）

| # | 声明 | 证据 | 结论 |
|---|---|---|---|
| T11 | `featureAtoms.test.ts` 硬编码原子 id | `featureAtoms.test.ts:40-41`：`expect(atomForFile('parser/_scanner.py')?.id).toBe('scan-and-parse'); expect(atomForFile('backend/backend/store.py')?.id).toBe('scan-api')` | ✅ 属实 |
| T12 | C2 覆盖测试 | `featureAtoms.test.ts:47-52`：遍历 fixture 每个非噪声非 `__init__` 模块，必须 `atomForFile` 命中 | ✅ 属实 |
| T13 | manifest 路径必须存在于 fixture | `featureAtoms.test.ts:54-62`：`moduleIds.has(file)` + 不得命名 `/tests/`/`/fixtures/` 文件 | ✅ 属实 |
| T14 | `graphToFeatureFlow.test.ts` 硬编码原子数/名字/files/边数 | `graphToFeatureFlow.test.ts:28`（`toHaveLength(2)`）、`:32-34`（name `'扫描并解析代码库'`、files `['parser/_scanner.py','parser/_ports.py']`）、`:42`（`unassignedCount` toBe(1)）、`:106`（`portCount` toBe(1)）、`:114`（files `['backend/backend/app.py']`）、`:131`（真实扫描 `unassignedCount` toBe(17)）、`:134-135`（names 含两个中文名）、`:142`（edges `toHaveLength(2)`） | ✅ 属实 |
| T15 | `Inspector.test.tsx` 硬编码原子节点 id | 复核：`Inspector.tsx` 只 import `../api/types`、`../lib/graphToFlow`、`../lib/depthScore`（grep 实查，无 manifest import）——`atom:scan-api` 等是**合成组件输入**，非 manifest 派生，AI 重生成不影响它 | ⚠️ **不属耦合集**（评审 F2 更正）：移出 Policy A 改动范围 |

**结论（T11-T14，评审 F2 更正）**：前端 **2 个**测试文件（`featureAtoms.test.ts`、`graphToFeatureFlow.test.ts`）硬编码当前手写 manifest 的具体内容；`Inspector.test.tsx` 不在耦合集，不动。AI 重生成 manifest 若分组/命名变化，前 2 个测试必挂。→ §6 R1（Policy A）的依据。

### 2.3 代码真值 — fixture 模块计数

命令（2026-08-28 实查）：
```
python -c "import json; g=json.load(open('frontend/src/__tests__/fixtures/deep-module-mapper.graph.json',encoding='utf-8')); ids=[m['id'] for m in g['modules']]; ..."
```
输出摘录：
```
total modules: 29
noise: 16          # 含 /tests/ 或 /fixtures/
init: 4            # 以 __init__.py 结尾
production: 11     # 其余
prod ids: ['backend/backend/app.py','backend/backend/models.py','backend/backend/scanner.py','backend/backend/store.py','parser/__main__.py','parser/_diagnostics.py','parser/_edges.py','parser/_external.py','parser/_ports.py','parser/_scanner.py','parser/_schema.py']
```
结论：✅ 属实。现 manifest 覆盖 12 文件（11 生产 + `parser/__init__.py`），16+4 噪声未覆盖 → `unassignedCount=17`（与 T14 `:131` 一致）。**新增 `backend/backend/aggregate/*` 后此 fixture 必须重生成**（否则 C2 断言 T12/T13 挂）。

### 2.4 环境真值 — editable install 与 import 解析（实现前先决条件）

命令（2026-08-28 实查）：
```
python -m pip show deep-module-mapper-backend deep-module-mapper-parser | grep -E "^(Name|Version|Location|Editable)"
git worktree list
python -c "import backend, parser; print('backend:', backend.__file__); print('parser:', parser.__file__)"
```
输出摘录：
```
Name: deep-module-mapper-backend   Editable project location: C:\Users\liyongquan\agent panel\deep-module-mapper-issue-10\backend
Name: deep-module-mapper-parser    Editable project location: C:\Users\liyongquan\agent panel\deep-module-mapper-issue-10\parser
git worktree list → 仅主 checkout: C:/Users/liyongquan/agent panel/deep-module-mapper  500ad5b [master]
import backend → None（namespace 包，无 __init__）；import parser → <本仓库>\parser\__init__.py
```
结论：✅ 属实。**两个 editable install 都指向 `deep-module-mapper-issue-10`**（评审复核已实测：仓库根 `pytest backend/tests` 于 conftest `ModuleNotFoundError`，与预测逐字一致；且 `deep-module-mapper-issue-10` 目录**已不存在**——死路径）。**实现前必须在新建 worktree 里 `pip install -e parser -e backend` 重指向，且先于 §8.3 step 1 的 `pytest` 全绿**（环境变更，执行前与用户确认——Q2 用户已确认）。重指向后 `backend` 顶层名仍由本地 namespace（仓库根 `backend/`）先命中（editable finder 是 `sys.meta_path.append`，在 PathFinder 之后），故 §5.10 两种调用形式**从仓库根都能跑**，但**均依赖 cwd=仓库根**，README 须注明。

### 2.5 服务器真值 — Ollama 可达性（2026-08-28 实查）

命令：
```
curl -s --max-time 5 http://127.0.0.1:11434/api/tags
```
输出摘录：
```
models: ['my-assistant:latest', 'my-assistant-bak-0827:latest', 'qwen3:8b']
```
结论：✅ 属实。`my-assistant`（qwen3:8b）在本机 127.0.0.1:11434 可达。调用模式先例：`verify-layer-A.sh` 直接 `POST /api/chat`（`{"model","messages","stream":false}` → `d["message"]["content"]`）。

### 2.6 GitHub 状态

- issue #11：状态 open、无 assignee、0 评论；body 含验收标准与「CORRECTION (coordinator, 2026-08-28)：后端无既有 AI provider 接口，必须新建」。
- 仓库 remote：`origin https://github.com/li-yongqvan/deep-module-mapper.git`；head `03cc71d [master]`（评审期间推进，map.md 记录聚合=纯 AI、无人工纠错、人工价值在重组层——与 U1 一致）。

### 2.7 未复核项

- **DeepSeek 响应形状 `choices[0].message.content` 与 base URL `https://api.deepseek.com/v1`**：任务确认、未实连测试（本环境无 API key 做只读验证）。真实端到端验证时确认。
- **本地模型 16K 上下文**：记忆（`local-llm-benchmark-baseline`）记 num_ctx 已升 16384；模型原生 40960。digest 12K 字符预算按保守侧设计。
- **轻量 digest 的失效阈值**：ports-only ≈150-250 字符/模块的估算为设计推演，未对真实大项目实测——§5.3 给阈值，真实端到端时用自扫描（约 21 生产文件）验证预算充足。

---

## §3 决策记录

| 编号 | 决策问题 | 定案 | 依据 |
|---|---|---|---|
| D1 | AI 聚合主力用哪个 API？ | **DeepSeek（OpenAI 兼容协议）** | 用户确认（2026-08-28，AskUserQuestion 选「DeepSeek / 其他 OpenAI 兼容」）。备选：Anthropic/OpenAI（未选：用户自述需国内直连方便、预算敏感）。 |
| D2 | 聚合在哪里跑？ | **CLI 脚本**（`python -m backend.backend.aggregate <repo>`） | 用户确认（2026-08-28，AskUserQuestion 选「CLI 脚本（推荐）」）。备选：后端端点 `POST /api/aggregate`（未选：需改 `featureAtoms.ts` 为运行时 fetch，动契约加载；key 进服务器；改动面大）。 |
| D3 | AI 重生成的自扫描 manifest 是否本 PR 提交？ | **提交**（前端测试改分组无关 + 刷 fixture） | 用户确认（2026-08-28，AskUserQuestion 选「提交 AI 重生成的 manifest（推荐）」）。备选：不提交留人审（未选：用户要一次 PR 完成 drop-in 验收）。 |
| D4 | 真实验证方式？ | **有 DeepSeek key，做真实端到端** | 用户确认（2026-08-28，AskUserQuestion 选「我有 DeepSeek key，做真实端到端」）。key 由用户自己写进环境变量，不回显给执行代理。 |
| D5 | 本地模型职责 | **学习角色**：聚合尝试（best-effort）**只为学习**——产出自己的答案，与云端权威答案对比、反思差异；**永不负责产品聚合、永不充当权威 manifest 来源** | 用户确认（2026-08-28，任务说明原话 + U6：本地模型目的是训练/学习，不承担聚合任务）。 |
| D6 | manifest 契约与红线 | 契约 `FeatureAtom` 形状不可改；drop-in only | handoff-ai-aggregation.md:96-101（红线段）+ issue #11 body。 |
| D7 | provider 抽象位置 | 新建 `backend/backend/aggregate/providers.py`，协议 + 两实现 + `get_provider()` 一处换 | handoff:47-51（「必须新建，没有可复用的」）+ 探索证实后端零 AI 代码（§2.1 T5）。 |
| D8 | retry/repair 策略 | 传输错误**总尝试 3 次（=1 首次 + 2 重试，1s,2s 退避）**；JSON 畸形/校验失败 → 1 次 repair pass；仍败 → 失败 | handoff:60 + 评审 F11（措辞统一 attempts 计数）。 |
| D9 | **失败行为（U1，覆盖原验收回退条款）** | **AI 聚合失败 → 明确报错 + 提示重试；不回退手工 manifest，不写任何 manifest**。手写 `feature-atoms.json` 是 #8 脚手架，非兜底、非最终形态 | 用户确认（2026-08-28，U1 原话）。**覆盖 issue #11 验收「回退手工 manifest」**；评审 F10（source=manual）前提已消失，不再需要 sourceHistory。 |
| D10 | 训练采集格式 | sidecar `feature-atoms.local.json` + `--training-log` JSONL（记录**本地模型实际看到的 digest** 字节级） | 用户确认（2026-08-28，D5 直接推论 + 评审 F3）。 |
| D11 | **质量对拍 = 核心交付物（U2/U4）** | 聚合结果 vs 手写 manifest（ground truth）对拍；指标 = **文件正确归入对应功能原子的占比**；进报告 + stdout + 最终汇报 | 用户确认（2026-08-28，U2/U4 原话）。 |
| D12 | **digest 轻量方案（U3）** | 只喂 路径 + imports + 端口签名/params/docstring（**不含全文 excerpt**）；本地 12K / API 40K 预算；标注失效阈值 | 用户确认（2026-08-28，U3「建议先做轻量」）。备选：全文方案（未选：只能处理小项目）。 |
| D13 | **失败 UX（U5）** | 模型挂了 → 明确「AI 聚合失败，可重试」+ 错误详情 + 报告路径 + 退出码区分，**不静默** | 用户确认（2026-08-28，U5 原话）。 |
| D14 | **本地模型学习机制（U6）** | **对比学习**：本地模型用本地 digest 产出自己聚合尝试 `local_out` → 云端成功时用 LEARN prompt 让本地模型**反思「与云端答案为何不同、漏了什么」** → 尝试 + 云端答案 + 反思一并入训练日志；best-effort，永不阻塞权威路径 | 用户确认（2026-08-28，U6 原话「看一下云端大模型给出的答案和自己的答案为什么不同，让它去学习一下」）。 |

---

## §4 范围收敛与明确不做

| 项 | 决策 | 依据 |
|---|---|---|
| 交付 CLI 聚合工具 | 做 | D2；issue #11 验收「AI 聚合路径」 |
| provider 抽象（新建） | 做 | D7 |
| prompt 工程（强结构+few-shot+JSON+repair） | 做 | handoff:55-64 |
| **失败 = 明确报错 + 提示重试（不回退手工）** | 做 | D9（U1） |
| **聚合质量对拍 vs 手写 manifest = 核心交付物** | 做 | D11（U2/U4） |
| **轻量 digest（路径+imports+端口，标注失效阈值）** | 做 | D12（U3） |
| 测试（mock 模型/畸形/失败路径/drop-in/对拍） | 做 | issue #11 验收 + D11 |
| README 文档化（config/运行/失败行为/重跑/质量对拍） | 做 | issue #11 验收 |
| 提交 AI 重生成的自扫描 manifest | 做 | D3 |
| 前端测试改分组无关 + 刷 fixture | 做 | D3（§2.2 T11-T14 证实必要） |
| **后端 `/api/aggregate` 端点** | **不做** | D2（用户选 CLI） |
| **画布评审端点** | **不做** | handoff:100（后续 ticket） |
| **改 parser 公共 API** | **不做** | handoff:97 红线 |
| **改 `/api/scan*` 三端点** | **不做** | handoff:98 红线 |
| **改 manifest 契约** | **不做** | handoff:99 红线（drop-in only） |
| **前端生产代码** | **不做** | D2 推论 + 红线意图（Policy A 只动测试+fixture+manifest 数据） |
| **回退手工 manifest 的降级** | **不做** | D9（U1）——不回退，明确报错+提示重试 |
| **人工纠错聚合结果** | **不做** | U1（聚合=纯 AI） |

**范围与规格偏离 / 验收条款覆盖**：
- issue #11 原文「本地模型 clusters files into functional atoms」→ 用户 2026-08-28 改为「API 主力 + 本地训练采集」（D5）。
- issue #11 验收「模型不可达/输出畸形时**回退手工 manifest**」→ 用户 2026-08-28 **显式覆盖**为「明确报错 + 提示重试，不回退」（D9/U1）。PR description 须引用这两处用户原话（评审 F13）。

**跨票并行隔离**：当前 `git worktree list` 仅主 checkout（03cc71d）。本票 worktree = `.claude/worktrees/worktree-issue-11-ai-aggregation`，与主 checkout 物理隔离。无共享装配点冲突。

---

## §5 实现方案

### 5.1 模块布局（新建 `backend/backend/aggregate/`）

| 文件 | 职责 |
|---|---|
| `__init__.py` | 公共面：`run_aggregation(...) -> int` |
| `__main__.py` | CLI：argparse → `main(argv) -> int`（镜像 `parser/__main__.py:16-30` 先例，§2.1 T9） |
| `config.py` | `EnvConfig` dataclass + `load_env_config()`（env-only，§2.1 T5/T6 惯例） |
| `digest.py` | `build_digest(graph, root, *, total_chars=...) -> str`：**轻量**（路径+imports+端口），滤噪声、确定性截断阶梯（§5.3） |
| `prompt.py` | `SYSTEM_PROMPT` / `USER_TEMPLATE` / `REPAIR_TEMPLATE` + `build_prompt(digest)` |
| `validate.py` | `FeatureAtom`/`FeatureAtomManifest`（pydantic, `extra="forbid"`）+ `validate_manifest()` |
| `providers.py` | `Provider` Protocol + `ProviderResult` + `retry_with_repair` + `OpenAICompatProvider`/`OllamaProvider` + `get_provider()` |
| `compare.py` | `compare_to_ground_truth(ai, gt) -> ComparisonResult`：**质量对拍指标**（D11/U2） |
| `runner.py` | `run_aggregation`：scan → digest → providers → validate → **compare** → write → report（唯一编排面） |
| `report.py` | `Report` pydantic + `build_report`/`write_report` |
| `training.py` | `TrainingRecord` + `append_training_log(jsonl)` + `write_local_sidecar` |
| `_http.py` | `post_json(url, headers, payload, timeout)`：urllib 网络唯一触点（测试 monkeypatch 点） |

**深模块原则**：`runner.py` 是唯一编排面；provider 换 = `get_provider()` 一处改（§6 R3）；校验/对拍共享；`_http.py` 唯一网络触点。

### 5.2 Provider 抽象（providers.py）

```python
class Provider(Protocol):
    name: str
    def generate(self, system, user, *, temperature=0.1) -> ProviderResult: ...
@dataclass
class ProviderResult: text: str|None; ok: bool; error: str|None; attempts: int
```
- `OpenAICompatProvider(base_url, api_key, model, ...)` → `POST {base}/chat/completions`，`Authorization: Bearer <key>`，取 `choices[0].message.content`（DeepSeek，权威）。依据：D1、§2.7 响应形状（待实连确认）。
- `OllamaProvider(host, model, ...)` → `POST {host}/api/chat`，`{"model","messages","stream":False,"options":{"temperature":0.1}}`，取 `message.content`。依据：§2.5 实查可达 + `verify-layer-A.sh` 调用模式。
- 传输用 stdlib `urllib.request`（无新运行时依赖，§6 R3）；测试注入 FakeProvider 或 monkeypatch `_http.post_json`。⚠️ urllib 默认走 Windows 注册表代理（本机实测 `http://127.0.0.1:7897`，`proxy_bypass('127.0.0.1')=True` → 本地 Ollama 调用安全、DeepSeek 走代理符合预期）；`_http.py` 仍显式构造 `ProxyHandler`（或 README 注明 `NO_PROXY` 含 `127.0.0.1`）兜底环境差异（评审 F8）。

### 5.3 输入 digest（digest.py）——轻量方案（D12/U3）

**选择**：轻量 digest = 每个模块 **文件路径 + imports + 端口（kind/name/signature/params/docstring）**。**不含全文 excerpt**。

**理由**（U3）：qwen3:8b 上下文有限（~16K），全文喂大项目必爆；端口签名 + docstring + imports 已含「这文件干什么、依赖谁」的核心聚类信号；能塞下更大项目。

**结构**（确定性 JSON）：
```json
{ "repo": "deep-module-mapper",
  "modules": [
    { "id": "parser/_scanner.py",
      "imports": ["ast", "tokenize", "parser/_edges.py"],
      "ports": [
        { "kind": "function", "name": "scan_codebase", "signature": "(root_path) -> dict",
          "params": ["root_path"], "docstring": "Return a Graph dict..." } ] }
  ] }
```
- `imports`：从 graph `edges` 提取（`source==id` 且 `kind ∈ import|from_import` → `target`；外部包 target 也列入，§2.1 T16）。
- 过滤：仅非噪声模块（排除含 `/tests/`、`/fixtures/` 的 id）——模型无法命名噪声文件。
- **确定性截断阶梯**（超预算逐级丢，永不丢 id/imports）：
  1. 丢所有 `docstring`
  2. 丢所有 `params`（保 signature）
  3. 端口只剩 `{kind, name}`
  4. 丢弃最长端口条目（保留高信号端口）——极端情况兜底
- 预算：本地 `TOTAL_DIGEST_CHARS=12000`（§2.7 保守适配 16K）；API `API_TOTAL_DIGEST_CHARS=40000`（评审 F3）。两 provider 同结构、不同预算，各自跑同一条截断阶梯。
- **失效阈值（U3 要求标注）**：ports-only 约 150-250 字符/模块 → 12K 预算下约 **50-80 模块**前 docstring 齐全、约 **100-120 模块**后 params 开始丢；>200 模块仅剩 id+imports+签名。**自扫描（~21 生产文件）预算充足**。真实端到端时用自扫描验证，报告 `warnings` 输出截断级别（INV14）。

### 5.4 prompt 工程（prompt.py）

- **SYSTEM**（常量）：强调「只输出合法 JSON、无任何多余文本」+ 9 条硬规则：id=kebab 英文唯一；name/description=中文一句（≤12/≤40 字）；files **必须原样来自输入**；**每个生产模块恰好出现在一个原子**（C2 覆盖）；**禁用测试/fixture 路径**；倾向深模块（少量原子、紧耦合文件同组）。
- **USER**：含 digest + few-shot 示例 + 期望 JSON 骨架。用 `{{DIGEST}}` 占位符 `.replace`（避免 f-string 花括号冲突）。
- **REPAIR**：把原始输出 + 错误明细喂回，要求修正后只输出 JSON。
- 依据：handoff:55-64（模型 prompt 纪律弱，实测会展开解释、可能不输出合法 JSON）。

### 5.5 校验（validate.py）

pydantic（所有字段 `min_length=1`，`extra="forbid"` 精确 drop-in）+ 后校验：
1. id 唯一；2. 字段非空；3. 无文件跨原子；4. **files 必须是真实 module id**（拒绝编造路径）；5. **绝不命名噪声文件**；6. **C2 覆盖**：每个生产模块（非噪声且非 `__init__.py`）恰好出现一次（缺则报未覆盖列表）；`__init__.py` 可选。
- 返回 `ValidationResult{ok, errors, manifest, coverage}`。
- 依据：§2.2 T12/T13（前端测试不变量，逐条镜像）。

### 5.6 retry/repair/失败（providers.py + runner.py）

- `retry_with_repair(provider, system, user, max_transport_attempts=3, repair_once=True)`：传输错误（连接/超时/429/5xx）**总尝试 3 次（=1 首次 + 2 重试，退避 1s,2s；4xx 校验错误不重试）**；首次拿到文本但输出无效 → 1 次 repair；仍败 → `ok=False`。
- 两 provider 同一策略；**本地失败不致命**（仅记录训练采集）。
- **决策树（D9/U1：无 manual-fallback）**：
  ```
  API ok + 校验通过 → compare（有 GT 时）→ 写权威 manifest（source=ai）→ 报告 status=ok → 退出 0
  API ok 但 repair 后仍无效 / API 传输失败（重试后）→ 明确报错 + 「AI 聚合失败，可重试」→ 退出 2
  （不回退手工 manifest、不写任何 manifest；既有脚手架文件原样保留，非降级结果）
  ```
- **本地学习流程（D14/U6，best-effort，永不阻塞权威路径）**：
  1. 本地模型用**本地 digest** 产出自己的聚合尝试 `local_out`（与云端同任务、同 USER_TEMPLATE）。
  2. 云端成功时：用 **LEARN prompt**（含 `local_out` + `api_out` + 差异提示）让本地模型**反思差异**——漏了什么信号？为何云端分组更好？产出 2-5 句学习笔记。
  3. `local_out` + `api_out` + 反思一并入训练日志（`--training-log`）与 sidecar；**本地答案永不写权威 manifest**。
  4. 本地不可达/失败 → 跳过学习步骤，不影响云端权威路径与退出码。
- **写 `--output`/`--report` 前 `parent.mkdir(parents=True, exist_ok=True)`**（镜像 `parser/__main__.py:26` 先例——任意仓库可能无 `frontend/src/manifest/`，评审 F9）。
- 依据：D8/D9。

### 5.7 报告与训练采集（report.py + training.py + compare.py）

- **报告**（默认 `<output.parent>/feature-atoms.report.json`）：
  - 成功：`{schemaVersion, generatedAt, status:"ok", repo:{path,modulesScanned,productionModules}, manifest:{written:true, source:"ai", path, atomCount, coverage}, quality:{groundTruthPath, accuracy, ...（见下）}, providers:{api:{ok,attempts,error}, local:{ok,attempts,error,parsed,sidecar}}, warnings}`。
  - 失败：`{schemaVersion, generatedAt, status:"failed", repo:..., manifest:{written:false}, error, providers:{api:{...}, local:{...}}, warnings}`。
  - stdout/stderr 人类可读摘要。
- **质量对拍（D11/U2，核心交付物）**：`compare_to_ground_truth(ai, gt)`——
  - 对每个 GT 原子，找与之**文件交集最大**的 AI 原子（best-match）；GT 文件落在「其 GT 原子 ∩ 匹配 AI 原子」中 → **正确归入**。
  - `accuracy = 正确归入文件数 / GT 生产文件总数`。
  - 附加：`ai_missed`（GT 有、AI 无）、`ai_extra`（AI 有、GT 无——如新增 aggregate/* 模块、`__init__.py`）、GT/AI 原子数、逐原子 best-match 表。
  - GT 来源：默认 `--output` 的既有内容（自扫描时即手写 manifest）；`--compare PATH` 可显式指定。
  - **新模块（aggregate/*）在 `ai_extra` 中不计入 accuracy**（无 GT 参照）；报告注明。
- **本地 sidecar**（`feature-atoms.local.json`）：本地模型输出（解析成 manifest 或 `{ok:false,error,raw}`），**权威路径永不读取**。
- **`--training-log`**（追加 JSONL，UTF-8、不覆盖、容忍已有），每次运行写 3 类记录（同 `run_id` 关联）：
  - `role="api"`：`{ts, run_id, repo, role, model, prompt, raw_output, parsed, ok}`（云端权威答案）
  - `role="local"`：`{ts, run_id, repo, role, model, prompt, raw_output, parsed, ok, api_reference}`（本地尝试；`prompt` 内联**本地 digest**，评审 F3：训练对齐 = 本地模型实际看到的输入）
  - `role="learn"`（D14/U6）：`{ts, run_id, repo, role, model, prompt, input:{local_output, api_output}, raw_output, ok}`（对比学习反思）
- **LEARN prompt（D14/U6）**：把 `local_out` + `api_out` 喂给本地模型，要求「分析差异：哪些文件分组不同？漏了什么信号（imports/docstring/同能力）？2-5 句学习笔记」——宽松格式，不要求严格 JSON（学习材料，非产品工件）。

### 5.8 CLI 面（__main__.py）

```
python -m backend.backend.aggregate <repo_path>
  --output PATH       默认 <repo>/frontend/src/manifest/feature-atoms.json（解析在被扫仓库下，§6 R6）
  --compare PATH      显式指定 ground truth manifest（默认：--output 既有内容即 GT）
  --dry-run           打印 manifest + 对拍指标，不写盘
  --skip-local        不调本地模型/不写 sidecar
  --training-log PATH 追加 JSONL
  --report PATH       默认 output 旁
```
env：`LLM_API_BASE`（默认 `https://api.deepseek.com/v1`）、`LLM_API_KEY`（无默认，**缺则无法调用 API → 致命退出 1，不进入聚合**；§8.1 测试钉死此语义，评审 F4）、`LLM_MODEL`（默认 `deepseek-chat`）、`OLLAMA_HOST`（默认 `http://127.0.0.1:11434`）、`OLLAMA_MODEL`（默认 `my-assistant`）、`LLM_TIMEOUT`/`OLLAMA_TIMEOUT`（60/120s）。

**退出码（D9/U5，评审 F4 并入）**：
- `0` — 权威（AI）manifest 已写，含质量对拍（有 GT 时）。
- `1` — 致命：坏路径 / 扫描失败 / 缺 `LLM_API_KEY`（配置/输入错误，不降级）。
- `2` — AI 聚合失败（重试后仍败）→ **明确报错 + 「AI 聚合失败，可重试」**；不写任何 manifest；报告 status=failed。

### 5.9 前端改动（Policy A，D3，评审 F1/F2/F5 落地）

- **耦合集 = 2 个测试文件**（评审 F2）：`featureAtoms.test.ts` + `graphToFeatureFlow.test.ts`。`Inspector.test.tsx` **不动**（§2.2 T15 复核：无 manifest 耦合）。
- `featureAtoms.test.ts`：删除 `:40-41` 的**具体 id 断言**；保留 `:47-52` C2 覆盖、`:54-62` 路径真实性、噪声排除。`:42-44` 噪声/未知未分配断言保留。
- `graphToFeatureFlow.test.ts`（评审 F1 断言级规格）：合成 `baseGraph` 本身就是当前 2 原子分组的编码，测试内 **import `FEATURE_ATOMS`/`atomForFile`，期望值从 manifest 动态推导**——原子节点数 = `new Set(baseGraph 生产模块 map atomForFile(m.id)?.id)` 的 size；`:32-34/:106/:114` 的中文名/files/portCount 改为按运行时 manifest 断言（保留契约形状、节点 id 前缀 `atom:`、唯一性）；`:42/:44` 噪声不变量保留。
- **`unassignedCount` 数值断言动态化**（评审 F5）：`:131` 的 `toBe(17)` 在新 fixture + AI manifest 下必挂，改为动态计算（噪声数 + 未覆盖 init 数）。
- `fixtures/deep-module-mapper.graph.json`：用 parser CLI 重生成（`python -m parser . --output frontend/src/__tests__/fixtures/deep-module-mapper.graph.json`，评审实测可用）。
- `frontend/src/manifest/feature-atoms.json`：AI 重生成后提交（drop-in）。
- **三方同 commit 同绿**（评审 F7）：测试改写、fixture 重生成、AI manifest 必须同一次提交——旧 manifest + 新 fixture 会让 C2 红。
- **生产代码零改动**：`featureAtoms.ts`、`graphToFeatureFlow.ts`、`recompose/*`、`App.tsx` 全不动。
- **失败 UX 说明（U5）**：聚合的「UI」= CLI 输出与报告（前端生产代码红线不动）；失败时 CLI 明确打「AI 聚合失败，可重试」。若后续要在产品 UI 内呈现聚合失败，属独立 ticket（已知缺口，§7 INV15 记录）。

### 5.10 文档

- `backend/README.md`：AI 聚合 CLI 章节（env 表、用法、**失败行为（明确报错+提示重试，不回退手工）**、退出码、**质量对拍指标与解读**、重跑）；注明两种调用形式（§2.4）**且均依赖 cwd=仓库根**。
- `frontend/README.md`：手工 JSON 段落改为「manifest 由 AI 聚合 CLI 生成（#11）」。
- **PR description** 显式引用 §4 偏离/验收覆盖登记 + D1/D5/D9 用户 2026-08-28 原话（评审 F13）——issue #11 body 字面仍写「本地模型产出 manifest」「回退手工」，防 reviewer 按字面卡验收。
- 可选：修 `backend/pyproject.toml:14` `httpx2` → `httpx` 笔误（§2.1 实查确认）。

---

## §6 关键设计裁决（【决策】，含理由与备选）

**R1 — 前端测试放松（Policy A）**
问题：AI 重生成 manifest 会改变分组/命名，前端 **2 个**测试硬编码旧内容（§2.2 T11-T14；`Inspector.test.tsx` 无 manifest 耦合，评审 F2）必挂，怎么处理？
定案【决策】：**Policy A——把这 2 个测试的硬编码断言改为分组无关**（保留契约/覆盖/形状断言，按评审 F1 断言级规格落地），并重生成 fixture；`Inspector.test.tsx` 不动；前端生产代码零改动。
理由：D3（用户选提交 AI manifest）；「AI 提议」意味着不应强制 AI 复刻手写内容；只动测试+数据文件不违反「不改消费管线」红线意图。
备选：Policy B（seed 手写 id/名字 + 后处理折叠新文件进旧原子）——**不选**：脆弱、约束 AI 分组自由、违背北极星。

**R2 — 训练对齐存本地 digest，API 可更大预算（评审裁决 F3）**
问题：本地模型与 API 模型输入不同，训练数据如何对齐？
定案【决策】：**训练记录存"本地模型实际看到的 digest"（字节级）；API 用更大预算 `API_TOTAL_DIGEST_CHARS=40000`，本地保持 `TOTAL_DIGEST_CHARS=12000`**。同一 `USER_TEMPLATE`、同一结构、各自跑同一条截断阶梯。
理由：D5 训练目的要求 `(input=本地 digest, local_out, api_out)` 对齐——**对齐的是本地输入**；API 不应被本地 8B 预算限制（唯一担责路径）。
备选：同一 digest 字节级喂两模型——**评审否决**：12K 是为本地 16K 上下文的保守设计，对 DeepSeek 无意义。

**R3 — 传输用 stdlib urllib，不加依赖**
问题：后端无 HTTP client 依赖（§2.1 T5），需要新增网络能力。
定案【决策】：**用 `urllib.request` 封装在 `_http.py`，零新运行时依赖**。
理由：保持后端依赖清单不变；`_http.py` 是唯一网络触点，测试 monkeypatch 即可离线。
备选：加 `httpx`——**不选**：需动依赖（且 pyproject 现有 `httpx2` 笔误未修，§2.1）；本项目风格偏最小依赖。

**R4 — 校验对 API 与本地输出同等执行**
问题：本地输出是否也要过完整校验？
定案【决策】：**是**——校验共享，两 provider 输出走同一 `validate_manifest()`。
理由：权威 manifest 必须合法；训练数据（本地输出）也需知道是否解析成功、失败原因。
备选：本地只存原文不校验——**不选**：训练日志缺结构化错误信息。

**R5 — 失败行为：不回退手工，明确报错（U1/D9 重定）**
问题：模型挂了怎么处理？原设计回退手写 manifest，U1 明确禁止。
定案【决策】：**AI 聚合失败 → 明确报错 + 提示重试；不回退手工 manifest、不写任何 manifest；退出码 2（可重试）**；缺 key/坏路径 = 退出码 1（配置/输入致命，不进入聚合）。
理由：U1（手写 manifest 是脚手架非兜底）；缺 key 是配置错误，静默降级会掩盖 misconfiguration（评审 F4）。
备选：原「source=manual 降级」——**被 U1 否决**。

**R6 — 默认 `--output` 解析在被扫仓库下**
问题：`--output` 默认路径相对谁？
定案【决策】：**默认 `<repo_path>/frontend/src/manifest/feature-atoms.json`**（被扫仓库下）。
理由：本工具是「对任意代码库生成功能原子 manifest」，输出应落在被扫仓库的 manifest 位置；与手写版位置一致。
备选：默认相对 CWD——**不选**：在非仓库 CWD 下会乱写。

**R7 — digest 选轻量（U3/D12）**
问题：喂什么给模型？
定案【决策】：**轻量 = 路径 + imports + 端口（kind/name/signature/params/docstring），不含全文 excerpt**；确定性截断阶梯（docstring→params→端口细节）。
理由：U3「先做轻量」；8B 上下文有限，全文大项目必爆；端口+imports 已含聚类核心信号；失效阈值可量化（§5.3）。
备选：全文方案（短 excerpt 1200 字符）——**不选**：自扫描 21 文件 × 1200 = 25K 即超本地 12K 预算，大项目必爆，判断依据反而更差。

---

## §7 边界与不变量清单

| # | 不变量 | 防护层 | 依据 |
|---|---|---|---|
| INV1 | 每个生产模块恰好出现在一个原子（C2） | `validate_manifest()` 覆盖检查 + repair 喂错 | §2.2 T12 镜像；D8 |
| INV2 | 每个 `files` 条目都是真实 module id | 校验拒绝编造路径 | §2.2 T13 镜像 |
| INV3 | manifest 永不命名 `/tests/`/`/fixtures/` 文件 | digest 过滤 + 校验拒绝 | §2.2 T13 镜像 |
| INV4 | 本地模型永不写权威 manifest | `runner.py`：仅 API 结果写 `--output`；本地只写 sidecar | D5 |
| INV5 | **AI 聚合失败不写任何 manifest**（既有脚手架文件原样保留，非降级结果） | runner 失败即退出，明确报错 + 提示重试 | D9（U1） |
| INV6 | drop-in 形状（`{atoms:[{id,name,description,files}]}`） | pydantic `extra="forbid"` | §2.1 T1；红线 |
| INV7 | 前端生产代码零改动 | Policy A 只动测试+fixture+manifest 数据 | D3；红线意图 |
| INV8 | 确定性 digest | 截断阶梯确定性、可测 | §5.3 |
| INV9 | 缺文件不崩溃 | 读磁盘缺文件 skip+警告 | §5.3 |
| INV10 | 训练日志可追加不破坏已有内容 | JSONL append + UTF-8 | §5.7 |
| INV11 | 缺 `LLM_API_KEY` 为配置错误 → **致命退出 1**（不降级、不进入聚合） | CLI env 校验 + 测试钉死 | D9/评审 F4（修正原 INV11 的「降级到手动、退出码 2/3」矛盾） |
| INV12 | 已知缺口：digest 对超大代码库逐级丢 docstring/params（保 id+imports） | 确定性截断阶梯 + 报告 warnings 输出截断级别 | §5.3 |
| INV13 | **质量对拍指标在有 GT 时必算、必进报告** | `compare.py` + report.quality + 测试 | D11（U2/U4） |
| INV14 | digest 截断级别进报告 warnings | 阶梯输出截断元数据 | §5.3 |
| INV15 | **失败必须显式呈现**：stderr 明确「AI 聚合失败，可重试」+ 错误详情 + 报告路径，不静默 | CLI 失败分支 + 报告 status=failed | D13（U5） |
| INV16 | **本地模型=学习角色**：其聚合尝试永不写入权威 manifest；对比学习反思在云端成功时 best-effort 执行，本地不可达不阻塞 | runner 本地学习流程 + D5/D14 |

---

## §8 测试与验证计划

### 8.1 后端单测（`backend/tests/test_aggregate_*.py`，全离线 mock/monkeypatch）

| 文件 | 用例 |
|---|---|
| `test_aggregate_digest.py` | 滤噪声、含生产+init、**imports 提取（import/from_import 边）**、**确定性截断阶梯（docstring→params→端口细节）**、缺文件不崩 |
| `test_aggregate_validate.py` | 合法通过 / 缺覆盖拒绝 / 噪声文件拒绝 / 编造路径拒绝 / 跨原子重复拒绝 / id 重复 / 空字段 / `__init__.py` 可选 / `extra="forbid"` 精确 drop-in |
| `test_aggregate_happy.py` | fake API 返回合法 manifest → 文件按 `{atoms}` 写入、报告 status=ok、quality 字段、退出 0；本地采集写入 |
| `test_aggregate_repair.py` | 畸形 JSON → repair → 成功（attempts==2）；覆盖缺失 → repair → 成功；始终坏 → 退出 2 |
| `test_aggregate_failure.py` | **API 传输错（重试后）→ 明确报错 + 「AI 聚合失败，可重试」、不写任何 manifest、既有脚手架文件未动、报告 status=failed、退出 2**；缺 key → 退出 1 |
| `test_aggregate_compare.py` | **对拍指标**：已知 GT + 已知 AI → 精确 accuracy；GT 有 AI 无（missed）；AI 有 GT 无（extra 不计 accuracy）；逐原子 best-match 表正确 |
| `test_aggregate_local.py` | 本地输出入 sidecar（解析/原文）；本地失败不致命（manifest 仍来自 API、退出 0）；`--skip-local` 不调本地；training-log 追加 + 记录本地 digest；**对比学习（D14）：云端成功时 LEARN 反思入日志（role=learn），云端失败不跑反思，本地不可达跳过不阻塞** |
| `test_aggregate_cli.py` | `--dry-run` 不写盘、`--output` 覆盖、`--compare` 指定 GT、坏路径退出 1、缺 key 退出 1、默认 output 在被扫仓库下 |

### 8.2 前端测试（Policy A 后）

- 2 个测试文件（`featureAtoms.test.ts`、`graphToFeatureFlow.test.ts`，评审 F2）改分组无关后 `cd frontend && npm test` 全绿；`npx tsc --noEmit` 通过；`npm run lint`。

### 8.3 真实端到端（用户提供 LLM_API_KEY 写 env，不回显）

0. **前置（Q2，用户已确认）**：在新建 worktree 里 `pip install -e parser -e backend` 重指向（§2.4），并确认 `pytest backend/tests` 的 conftest 不再挂。✅ 已完成（2026-08-28：editable 指向 worktree，5 passed）。
1. `python -m pytest parser/tests backend/tests -q` 全绿（mock provider）
2. `cd frontend && npm test` 全绿 + `npx tsc --noEmit`
3. `python -m backend.backend.aggregate . --compare frontend/src/manifest/feature-atoms.json`（自扫描）→ DeepSeek 权威聚合 → 写合法 `feature-atoms.json`（drop-in、C2 覆盖）→ 报告 status=ok → **输出质量对拍指标（accuracy = 文件正确归入占比）**
4. 同一命令确认 Ollama `my-assistant` 产出**自己的聚合尝试** + **对比学习反思**（云端答案 vs 自己答案的差异分析，role=learn）入 sidecar/`--training-log`，不影响权威 manifest
5. **失败演示（U5/U1）**：临时把 `LLM_API_BASE` 指向不可达地址 → stderr 明确「AI 聚合失败，可重试」、不写任何 manifest、脚手架文件原样保留、报告 status=failed、退出 2
6. **最终汇报必须含**：聚合结果 vs 手写 manifest 的对拍数据（accuracy/missed/extra/原子数对比）——D11/U2 核心交付物

---

## §9 待评审焦点（Q1-QN）

- **Q1（已拍板）**：R1 Policy A 放松前端 **2 个**测试的硬编码断言（§2.2 T11-T14；`Inspector.test.tsx` 无 manifest 耦合，不动）——评审认可附 3 条件（F1/F2/F5），用户已书面确认。
- **Q2（已确认）**：实现前需在新建 worktree 里 `pip install -e parser -e backend` 重指向 editable installs（§2.4 实查指向已删除的 issue-10）。环境变更，执行前需用户确认——评审无异议，用户已确认。✅ 已执行。
- **Q3（未实连）**：DeepSeek 的 base URL / `choices[0].message.content` 响应形状未实连验证（§2.7）。真实端到端时确认；若失败，provider 抽象保证是单点改动。
- **Q4（U3 落地）**：轻量 digest（无 excerpt）对语义分组的判断力是否足够？对拍指标会给出客观答案；若 accuracy 偏低，后续加 excerpt 作为阶梯第 0 级（API 预算够）。
- **Q5（训练日志）**：`--training-log` 内联本地 digest 是否满足微调数据需求？裁决：内联可接受；后续量大再加 `--training-log-dir` 另存。
- **Q6（验收覆盖）**：issue #11 原文「本地模型产出 manifest」「回退手工 manifest」被用户 2026-08-28 覆盖（D5/D9，§4 登记）——评审确认授权成立，PR 引用原话（F13）。
- **Q7（新）**：质量对拍以「GT 原子 ↔ AI 原子 best-match 交集」定义 accuracy——是否认可此指标定义？（vs 逐文件字符串匹配：AI id/名字必然不同，无法直接比对，best-match 是客观可行的定义。）

---

## §10 评审意见采纳记录

评审：`magical-herding-swan-评审意见书.md`（2026-08-28，对抗评审 Pass 0–5，实测自 deep-module-mapper @ 500ad5b）。结论：**有条件通过**（阻塞 0 / 重要 5 / 建议 8）。用户 2026-08-28 确认通过；2026-08-28 五点补充（U1-U5）并入 v2。

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| F1 Policy A 断言级规格 | 重要→采纳 | §5.9 落地：graphToFeatureFlow.test.ts 从 `FEATURE_ATOMS`/`atomForFile` 动态推导断言 |
| F2 T15 耦合集判错 | 重要→采纳 | §2.2/T15 更正为 2 文件；§5.9 明确 Inspector.test.tsx 不动 |
| F3 R2 同 digest 过度约束 | 重要→采纳 | §6 R2 改道 + §5.3：API 用 `API_TOTAL_DIGEST_CHARS=40000`，训练记录存本地 digest |
| F4 缺 key 语义矛盾 | 重要→采纳 | §5.8 env 行改为「缺则直接致命退出 1，不进入降级」，与退出码/测试一致 |
| F5 unassignedCount 数值断言 | 重要→采纳 | §5.9 动态化 `:131 toBe(17)` |
| F6 截断未量化 | 建议→采纳 | §5.3 注明自扫描预算充足 + 截断阶梯量化（INV12/14） |
| F7 三方同 commit 顺序 | 建议→采纳 | §5.9 明示测试改写/fixture 重生成/AI manifest 同 commit 同绿 |
| F8 `_http.py` 代理行为 | 建议→采纳 | §5.2 显式 ProxyHandler 兜底 + README 注明 NO_PROXY |
| F9 `--output` 缺 mkdir | 建议→采纳 | §5.6 写盘前 `parent.mkdir(parents=True, exist_ok=True)` |
| F10 降级 source=manual 语义 | 建议→**被 U1 取代** | D9/U1 已删除 manual-fallback，sourceHistory 不再需要 |
| F11 retry 措辞歧义 | 建议→采纳 | D8/§5.6 统一为「总尝试 3 次（1 首次 + 2 重试）」 |
| F12 用户确认落档 | 建议→采纳 | grilling-decisions/issue-11-ai-aggregation-decisions.md（含 D1-D14 + 本表） |
| F13 PR 引用偏离登记 | 建议→采纳 | §5.10 PR description 显式引用 §4 覆盖登记 + D1/D5/D9 原话 |
| Q1 Policy A 触碰测试语义 | 认可附 3 条件 | 条件=F1/F2/F5，已落地 §5.9；用户已书面确认 |
| Q2 re-point 环境先决 | 认可无异议 | §2.4 增 issue-10 已删事实 + cwd 依赖说明；§8.3 增 step 0；用户已确认 |
| Q3 DeepSeek 未实连 | 认可 | 单点改动保证；真实端到端时验证 |
| Q4 digest 预算 | 裁决：按 F3 分离 | §6 R2/§5.3 落地 |
| Q5 training-log 内联 digest | 裁决：内联可接受 | §5.7 注明；后续量大再加 `--training-log-dir` |
| Q6 验收口径偏离 | 授权成立 | §4 覆盖登记保留；§5.10 PR 引用（F13） |

**v2 用户五点补充（U1-U5，2026-08-28）**：

| 项 | 结论 | 采纳落地 |
|---|---|---|
| U1 纯 AI、不回退手工 | 采纳 | D9/§5.6/§5.8/§7 INV5 重写：失败=明确报错+提示重试，不写任何 manifest |
| U2/U4 质量对拍=核心交付物 | 采纳 | 新 `compare.py`（D11）+ §5.7 quality 字段 + §8.3 汇报含对拍数据 + §7 INV13 |
| U3 轻量 digest | 采纳 | §5.3 重写（路径+imports+端口，无 excerpt）+ §6 R7 + 失效阈值标注（§2.7） |
| U5 失败 UX 显式 | 采纳 | §5.6/§5.7/§8.3 失败分支 + §7 INV15：stderr「AI 聚合失败，可重试」+ 报告 status=failed |
| U6 本地模型=学习角色（对比学习） | 采纳 | D5 更新 + D14 + §5.6 本地学习流程 + §5.7 role=learn + §7 INV16：聚合全交云端，本地产出自己答案并反思与云端差异 |

剩余建议（未采纳）：无——F6-F13 全部采纳；F10 被 U1 取代。

---

## 附录 A — 质量对拍指标定义（D11/U2 核心交付物）

`compare_to_ground_truth(ai_manifest, gt_manifest) -> ComparisonResult`

- 输入：AI 产出的 `FeatureAtomManifest` + ground truth（默认 = `--output` 既有内容，即自扫描的手写 manifest）。
- **best-match**：对每个 GT 原子 `g`，在 AI 原子中找 `argmax |g.files ∩ a.files|` 的 `a`（并列取交集中文件数最大；仍并列取先出现者，确定性）。
- **正确归入**：GT 文件 `f ∈ g.files` 且 `f ∈ matched_a.files`（即落在交集里）。
- **accuracy = 正确归入文件数 / |GT 生产文件|**（GT 生产文件 = 非噪声、非 `__init__.py` 的 GT 文件）。
- 附加输出：`ai_missed`（GT 生产文件但不在任何 AI 原子）、`ai_extra`（AI 原子中有、GT 无——如新增 `aggregate/*`、`__init__.py`，**不计入 accuracy**）、`gt_atoms`/`ai_atoms` 数、逐原子 best-match 表（GT id → AI id / 交集 / 正确数）。
- 说明：AI 的原子 id/名字必然与 GT 不同（AI 提议自由分组），故不用字符串匹配，用集合交集定义「对应」——客观、可复现、进报告。
