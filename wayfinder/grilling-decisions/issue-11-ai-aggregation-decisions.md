# Issue #11 AI 聚合 — 决策归档

> 用途：为设计文档 §3 的「用户确认」决策提供可复核落档（评审 F12）。
> 关联文档：设计文档 `wayfinder/design-doc-issue-11-ai-aggregation.md`；8-spec 规划书 `wayfinder/spec-issue-11-ai-aggregation.md`。
> 评审状态：`magical-herding-swan-评审意见书.md` 有条件通过（2026-08-28）；用户 2026-08-28 确认定稿；U1-U6 并入。

## D1-D14 决策表

| 编号 | 决策 | 定案 | 确认方式 |
|---|---|---|---|
| D1 | AI 聚合主力用哪个 API？ | **DeepSeek（OpenAI 兼容协议）** | 用户确认（2026-08-28，AskUserQuestion 选「DeepSeek / 其他 OpenAI 兼容」；弃选 Anthropic/OpenAI——需国内直连方便、预算敏感） |
| D2 | 聚合在哪里跑？ | **CLI 脚本**（`python -m backend.backend.aggregate <repo>`） | 用户确认（2026-08-28，AskUserQuestion 选「CLI 脚本（推荐）」；弃选后端端点 `POST /api/aggregate`——需改 `featureAtoms.ts` 运行时 fetch、key 进服务器、改动面大） |
| D3 | AI 重生成的自扫描 manifest 是否本 PR 提交？ | **提交**（前端测试改分组无关 + 刷 fixture） | 用户确认（2026-08-28，AskUserQuestion 选「提交 AI 重生成的 manifest（推荐）」；弃选不提交留人审） |
| D4 | 真实验证方式？ | **有 DeepSeek key，做真实端到端** | 用户确认（2026-08-28，AskUserQuestion 选「我有 DeepSeek key，做真实端到端」；key 由用户自己写环境变量，不回显执行代理） |
| D5 | 本地模型职责 | **学习角色**：聚合尝试（best-effort）只为学习——产出自己的答案，与云端权威答案对比、反思差异；**永不负责产品聚合、永不充当权威 manifest 来源** | 用户确认（2026-08-28，任务说明原话「我使用本地模型，更多的目的是出于训练我的本地模型…主要职责还是由使用API接口的大模型来完成」+ U6） |
| D6 | manifest 契约与红线 | 契约 `FeatureAtom` 形状不可改；drop-in only | handoff-ai-aggregation.md 红线段 + issue #11 body |
| D7 | provider 抽象位置 | 新建 `backend/backend/aggregate/providers.py`：协议 + 两实现 + `get_provider()` 一处换 | handoff:47-51「必须新建，没有可复用的」+ 探索证实后端零 AI 代码 |
| D8 | retry/repair 策略 | 传输错误**总尝试 3 次（=1 首次 + 2 重试，1s,2s 退避）**；JSON 畸形/校验失败 → 1 次 repair pass；仍败 → 失败 | handoff:60 + 评审 F11（措辞统一 attempts 计数） |
| D9 | **失败行为（U1，覆盖原验收回退条款）** | **AI 聚合失败 → 明确报错 + 提示重试；不回退手工 manifest，不写任何 manifest** | 用户确认（2026-08-28，U1 原话「AI 聚合失败 → 明确报错 + 提示重试，不回退手工」）；覆盖 issue #11 验收「回退手工 manifest」条款；评审 F10 前提消失 |
| D10 | 训练采集格式 | sidecar `feature-atoms.local.json` + `--training-log` JSONL（记录**本地模型实际看到的 digest** 字节级） | 用户确认（2026-08-28，D5 直接推论 + 评审 F3） |
| D11 | **质量对拍 = 核心交付物（U2/U4）** | 聚合结果 vs 手写 manifest（ground truth）对拍；指标 = **文件正确归入对应功能原子的占比**；进报告 + stdout + 最终汇报 | 用户确认（2026-08-28，U2/U4 原话「质量对比 = 核心交付物」） |
| D12 | **digest 轻量方案（U3）** | 只喂 路径 + imports + 端口签名/params/docstring（**不含全文 excerpt**）；本地 12K / API 40K 预算；标注失效阈值 | 用户确认（2026-08-28，U3「建议先做轻量」；弃选全文方案——只能处理小项目） |
| D13 | **失败 UX（U5）** | 模型挂了 → 明确「AI 聚合失败，可重试」+ 错误详情 + 报告路径 + 退出码区分，**不静默** | 用户确认（2026-08-28，U5 原话） |
| D14 | **本地模型学习机制（U6）** | **对比学习**：本地用本地 digest 产出自己聚合尝试 `local_out` → 云端成功时用 LEARN prompt 反思「与云端答案为何不同、漏了什么」→ 尝试 + 云端答案 + 反思一并入训练日志；best-effort，永不阻塞权威路径 | 用户确认（2026-08-28，U6 原话「看一下云端大模型给出的答案和自己的答案为什么不同，让它去学习一下」） |

## 评审采纳记录（magical-herding-swan-评审意见书，2026-08-28 有条件通过）

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| F1 Policy A 断言级规格 | 重要→采纳 | spec 规划书 §5.9：graphToFeatureFlow.test.ts 从 `FEATURE_ATOMS`/`atomForFile` 动态推导断言 |
| F2 T15 耦合集判错 | 重要→采纳 | 更正为 2 文件；Inspector.test.tsx 不动 |
| F3 R2 同 digest 过度约束 | 重要→采纳 | API 用 `API_TOTAL_DIGEST_CHARS=40000`，训练记录存本地 digest |
| F4 缺 key 语义矛盾 | 重要→采纳 | 缺 `LLM_API_KEY` → 致命退出 1，不进入降级 |
| F5 unassignedCount 数值断言 | 重要→采纳 | 测试动态化 `toBe(17)` |
| F6 截断未量化 | 建议→采纳 | §5.3 自扫描预算充足 + 截断阶梯量化 |
| F7 三方同 commit 顺序 | 建议→采纳 | 测试改写/fixture 重生成/AI manifest 同 commit 同绿 |
| F8 `_http.py` 代理行为 | 建议→采纳 | 显式 ProxyHandler 兜底 + README 注明 NO_PROXY |
| F9 `--output` 缺 mkdir | 建议→采纳 | 写盘前 `parent.mkdir(parents=True, exist_ok=True)` |
| F10 降级 source=manual 语义 | 建议→**被 U1 取代** | D9/U1 删除 manual-fallback，sourceHistory 不再需要 |
| F11 retry 措辞歧义 | 建议→采纳 | 统一为「总尝试 3 次（1 首次 + 2 重试）」 |
| F12 用户确认落档 | 建议→采纳 | 本文件（D1-D14 + 本表 + U1-U6） |
| F13 PR 引用偏离登记 | 建议→采纳 | PR description 显式引用偏离登记 + D1/D5/D9 原话 |
| Q1 Policy A 触碰测试语义 | 认可附 3 条件 | 条件 = F1/F2/F5；用户已书面确认 |
| Q2 re-point 环境先决 | 认可无异议 | 设计文档 §2.4 增 issue-10 已删事实 + cwd 依赖说明 |
| Q3 DeepSeek 未实连 | 认可 | 单点改动保证；真实端到端时验证 |
| Q4 digest 预算 | 裁决：按 F3 分离 | 设计文档 §6 R2/§5.3 落地 |
| Q5 training-log 内联 digest | 裁决：内联可接受 | 后续量大再加 `--training-log-dir` |
| Q6 验收口径偏离 | 授权成立 | 设计文档 §4 覆盖登记保留 |

## U1-U6 用户补充要求（2026-08-28）

| 项 | 内容 | 采纳落地 |
|---|---|---|
| U1 | **纯 AI**：聚合层 = 纯 AI 判断，不加人工纠错；AI 聚合失败 → 明确报错 + 提示重试，**不回退手工 manifest** | D9/决策树/退出码 2；不写任何 manifest；脚手架文件原样保留 |
| U2/U4 | **质量可验证**：用客观基准验收——手写 manifest 是 ground truth，AI 结果对拍，报「能正确归入对应功能原子的文件占比」；**聚合质量对比 = 核心交付物** | 新 `compare.py`（D11）+ report.quality + 真实端到端汇报含对拍数据 |
| U3 | **喂什么**：先做轻量（端口签名 + docstring + imports + 文件路径），标注选择、理由、失效项目规模 | D12 + digest.py（无全文 excerpt）+ 截断阶梯量化 |
| U5 | **降级呈现**：模型挂了 → 明确告诉用户「AI 聚合失败，可重试」，不静默 | D13 + CLI stderr + report status=failed |
| U6 | **本地模型=学习角色**：聚合完全交云端；本地产出自己答案，对比云端答案反思「为何不同、漏了什么」，从中学习；其答案永不用于产品 | D5 更新 + D14 + LEARN prompt + role=api/local/learn 三行成对采集 |
