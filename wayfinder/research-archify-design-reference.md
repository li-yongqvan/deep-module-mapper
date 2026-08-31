---
name: research-archify-design-reference
wayfinder: research
status: closed
ticket: "https://github.com/li-yongqvan/deep-module-mapper/issues/20"
---

## Question

[Archify](https://github.com/tt-a1i/archify) 作为一个「把代码库/系统描述转成可交互架构图」的 agent skill，它的设计思路是什么？它的「流程划分」和核心机制（typed JSON IR、校验回执、确定性渲染、Delta 对比）对 deep-module-mapper 有哪些可落地的参考价值？

## Scope

- 阅读 Archify 的 `SKILL.md`、`schemas/README.md`、`DESIGN.md`、`PRODUCT.md` 与 CLI 实现。
- 提炼其「生成 → 校验 → 预览 → 交付 → 迭代」流程的边界划分。
- 将其设计模式映射到 deep-module-mapper 的当前架构与路线图（#18 画线即校验、trace path、画布评审、schema 演进）。
- 产出一份可复现的落地参考原型，包含：
  - 一张用 Archify 生成的 deep-module-mapper 自身运行时架构图；
  - 一份可导入我们数据层的「图数据 JSON IR」样例与校验回执样例。

## Findings

### 1. Archify 的流程划分：AI 与渲染机的明确契约

Archify 把整个工作流切成 5 段，核心原则是：**AI 只写「事实 JSON」，布局/校验/交付交给确定性代码。**

```
生成 Generate → 校验 Validate → 预览 Preview(可选) → 交付 Deliver → 迭代 Iterate
```

| 阶段 | AI 做什么 | 机器做什么 | 关键纪律 |
|---|---|---|---|
| **Generate** | 读 schema + example，写一份 typed JSON IR | 无 | 不写坐标、不规划布局，≤12 主节点 |
| **Validate** | 按回执修复 | Schema 校验 + 几何校验 | `additionalProperties: false`，未知字段直接拒绝 |
| **Preview** | 无 | 桌面循环，只刷新通过校验的版本 | 失败保留 last-good |
| **Deliver** | 无 | 冻结规格 → 渲染 → 校验 → 原子替换 | 失败不上架，回执含 SHA-256 |
| **Iterate** | 改被诊断的 subject | 保持无关结构稳定 | 每次只应用一个诊断修复 |

### 2. Typed JSON IR：把图变成数据契约

Archify 的 IR 不是「画图的配置」，而是**语义事实**：

- 每个图类型（architecture/workflow/sequence/dataflow/lifecycle）有独立 schema；
- `schema_version` 显式声明，向后兼容是硬性承诺；
- `meta` 只放渲染器拥有的字段（locale、quality_profile、animation），不翻译作者内容；
- 所有语义集合（components、connections、nodes）使用稳定 `id`，支持 `#focus=`、`#relation=` 等深链接；
- `additionalProperties: false` 遍布每一层，杜绝「静默忽略错误字段」。

### 3. 校验回执：机器可读的失败报告

失败不是一句「重试」，而是一份 receipt：

```json
{
  "code": "clean-flow/edge-through-node",
  "severity": "error",
  "subject": { "collection": "connections", "index": 8, "from": "aggregator", "to": "ollama" },
  "evidence": { "obstacleId": "deepseek", "clearancePx": 2 },
  "supportedFixes": ["adjust fromSide/toSide", "set route/via", "move the component"]
}
```

这个格式可以直接被 AI 消费：知道改哪个对象、证据是什么、允许怎么修。

### 4. 确定性渲染与质量分档

- 布局是 renderer 的职责，AI 不排坐标；
- 自动路由有明确的「side contract」和「port spread」规则；
- `quality_profile` 分两档：`standard`（4 项检查）vs `showcase`（9 项检查，0 警告）；
- 导出保持「canonical」：不含 viewer 状态、动画、临时高亮。

### 5. Delta 对比：Before / Delta / After

`archify compare architecture base.json head.json` 产出：

- 变更前、变更差异、变更后三视图；
- 机器回执列出 added / removed / changed / moved / rerouted；
- 不推断风险、不影响范围，只陈述「图上哪些事实变了」。

## Recommendations for deep-module-mapper

| 我们的模块/路线图 | 当前状态 | 可借鉴的 Archify 模式 | 落地建议 |
|---|---|---|---|
| **数据层 / `design-data-schema.md`** | 已有 JSON schema，但版本、字段严格性未固化 | `schema_version` + `additionalProperties: false` + 兼容策略 | 为 graph IR 引入显式 `schema_version`；关闭未知字段；schema 变更走版本升级 |
| **#18 画线即校验** | 人在画布画线，当场校验真实依赖 | 校验回执格式（code + subject + evidence + supportedFixes） | #18 拒绝提示采用统一回执：规则码、代码证据、允许的修复方式 |
| **自动布局（dagre 后续优化）** | naive 网格 | 布局是 renderer 职责，AI/数据层不排坐标 | 自动布局模块与图数据解耦；端口 spread、side contract 可作为布局约束 |
| **trace path / 画布评审（路线图）** | 未实现 | `compare` 的 Before/Delta/After + 机器回执 | 现实视图 vs 自定义画布对比可采用「Delta 视图」；评审结果用结构化 receipt |
| **深度分 / 评分** | naive `maxLine/portCount` | `quality_profile` 分档 | 定义「够用」与「展示级」两档阈值，避免追求全绿 |
| **导出/分享（远期）** | Mermaid/DOT/JSON 已明确不做 | 自包含 HTML + 分享卡片 | 若未来需要汇报层，可复用 Archify 的「单文件 HTML + Share Card」思路，但保持现有 out-of-scope 决策 |
| **AI 聚合 (#11)** | DeepSeek 权威、Ollama 学习 | 证据纪律、不推断运行时影响 | 聚合结果的 manifest 也可带「证据来源」字段；拒绝降级文件 |

## Prototype artifacts

### A-1. 用 Archify 生成的 deep-module-mapper 运行时架构图

- **JSON 源**：`C:\Users\liyongquan\AppData\Local\Temp\deep-module-mapper.architecture.json`
- **HTML 产物**：`C:\Users\liyongquan\AppData\Local\Temp\deep-module-mapper.architecture.html`（729 KB，单文件可离线打开）
- **交付回执**：
  - specification SHA-256: `6e78db9768e2be5877236255ee02c78f0d60a4f5d648f968f4243611f5ddec05`
  - artifact SHA-256: `e518f70f78ff2e62afffd15591a1aacda244c585d009cbb933dac602c5dc0e2d`
  - checks: 9/9 showcase 通过，0 errors，0 warnings

该图包含三条 guided view：扫描主路径、AI 聚合路径、状态与持久化。

### B-1. 图数据 JSON IR 样例（拟合 deep-module-mapper 当前 API 输出）

如果我们把后端 `/api/graph` 的返回收紧为一份 typed IR，可以长成这样（节选）：

```json
{
  "schema_version": 1,
  "diagram_type": "architecture",
  "meta": {
    "title": "Deep Module Mapper 运行时架构",
    "locale": "zh-CN",
    "quality_profile": "showcase"
  },
  "components": [
    { "id": "frontend", "type": "frontend", "label": "Frontend", "sublabel": "React + Vite" },
    { "id": "backend",  "type": "backend",  "label": "Backend API", "sublabel": "Starlette" },
    { "id": "parser",   "type": "backend",  "label": "Python Parser", "sublabel": "AST" }
  ],
  "connections": [
    { "from": "frontend", "to": "backend", "label": "REST API" },
    { "from": "backend",  "to": "parser",  "label": "scan_codebase" }
  ]
}
```

### B-2. 拟议的 #18 校验回执样例

```json
{
  "ok": false,
  "code": "edge/reverse-dependency",
  "severity": "error",
  "subject": {
    "collection": "userCanvasEdges",
    "edgeId": "parser→backend",
    "from": "parser",
    "to": "backend"
  },
  "evidence": {
    "expectedDirection": "backend → parser",
    "sourceFile": "backend/backend/scanner.py",
    "line": 7,
    "snippet": "from parser import scan_codebase"
  },
  "supportedFixes": [
    "reverse edge direction",
    "remove edge",
    "mark as intentional architectural exception"
  ]
}
```

## Blocking

- 无前置阻塞。本研究文档基于已关闭的 #11（AI 聚合）与进行中的 #18（画线即校验）。
- 后续若要把「Delta 对比」或「汇报层」做成正式功能，需要单独 ticket + design-doc-for-review。

## Notes

- Archify 是**汇报/展示层**工具，**不能替代** deep-module-mapper 的拖拽重组画布。若产品级集成，建议只把它当作「导出精美图 / 架构评审对比」层，而不是替换 React Flow。
- `map.md` 已明确「多格式导出 Mermaid/DOT/JSON 不要」；Archify 的 HTML/PNG/SVG 导出不与此冲突，但方向上有重叠，需用户拍板是否纳入范围。
- 本研究中用于生成原型的 Archify skill 已全局安装至 `C:\Users\liyongquan\.claude\skills\archify`。

## References

- GitHub: https://github.com/tt-a1i/archify
- 本地 skill: `C:\Users\liyongquan\.claude\skills\archify/SKILL.md`
- 本项目相关：
  - `wayfinder/design-data-schema.md`
  - `wayfinder/design-doc-issue-18-recomposition-edge-check.md`
  - `wayfinder/map.md` → Open frontier #18
