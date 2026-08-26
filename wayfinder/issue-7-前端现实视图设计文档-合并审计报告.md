# 合并审计报告：issue #7 前端现实视图设计文档

- **审计对象**：《#7 Build frontend real-view with React Flow — 设计文档（供评审）》（`wayfinder/design-doc-issue-7-frontend-real-view.md`，2026-08-26）
- **合并来源**：
  1. `wayfinder/design-doc-issue-7-frontend-real-view-评审意见书.md`（评审方独立复核，2026-08-26）
  2. `C:\Users\liyongquan\Downloads\issue-7-前端现实视图设计文档-审计报告.md`（严格审查官视角，2026-08-26）
- **审计方法**：以当前工作树 `deep-module-mapper-frontend-real-view` @ `640dec3` 与公开仓库 `li-yongqvan/deep-module-mapper` 为真值源，对关键声明逐一实测，并叠加两份评审的交叉验证。
- **数据时点**：2026-08-26
- **合并审计结论**：**不予通过为执行基线**。存在 **5 项阻断缺陷、8 项重要问题、10 项次要问题**；修订后需复审。

---

## 一、总结论

设计文档在溯源纪律、范围收敛、红线约束上达到了项目内较高水准，未发现伪造 `file:line` 或把判断伪装成事实的情况，应予肯定。

但「事实可靠」不等于「可执行」。两份独立评审从不同镜头切入，发现了一个共同的致命问题：**文档里能直接执行的句子与真实环境对不上**；同时，对方评审在「真实数据灌进去会不会炸」这条线上挖得更深，补上了外部模块依赖边、同模块对多边重叠、轮询失败分支等关键盲区。

本次合并审计把两份报告的结论取并集、冲突处取更严解释，最终形成 5 项阻断缺陷。只有在全部修复并通过复审后，本文档方可作为执行基线。

---

## 二、阻断项（Blocker — 不修复不得开工）

### B1. 外部模块依赖边悬空：graphToFlow 会产出指向不存在节点的边

**实证链**（已独立复核）：

- `parser/_edges.py` 的第三方 import 分支会产出 `target = "requests"` / `target = "sample_pkg"` 这类边；
- 这些 `target` **不在** `modules` 数组中，只出现在 `externalModules` 数组（`schema.json:62-74` 已确认两数组分离）；
- 设计文档 §5.5 只为 `modules` 生成 React Flow 节点，**全文未提及 `externalModules` 的渲染或过滤策略**。

**后果**：React Flow 对指向不存在节点的边不予渲染并抛出警告。任何真实 Python 项目几乎必有第三方 import → 首屏就缺边，且控制台报错，直接违反验收标准「render the Graph as a React Flow canvas」。

**必须裁决（二选一，写进修订稿）**：
- (a) 将 `externalModules` 渲染为视觉上有区分度的节点（推荐：虚线边框/灰色，不进评分体系）；或
- (b) 在 `graphToFlow` 中过滤 target/source 不在 `modules` 中的边，并在 UI 显眼处显示「已折叠 N 条外部依赖」。

**连带修订**：§8.1 `graphToFlow` 测试必须增加「含 externalModules 的 Graph」用例；若选 (a)，§5.5 布局的节点计数公式与 §7 不变量 6 都要把外部节点算进去。

---

### B2. 把手语义定案与书面验收标准冲突，需用户书面确认

**实证链**：

- issue #7 验收标准原文：「Modules are rounded-rectangle nodes; **ports are small circular handles**」；
- handoff Steps §3 原文：「**One small circular port handle per public port**」；
- `UBIQUITOUS_LANGUAGE.md` 定义端口把手「代表一个模块的**输入或输出端口**」—— per-port 语义；
- §6.1 定案为每模块左右各一个 Handle。文档自己也在 Q1 中承认这是对 handoff 的偏离。

**缓解事实**：`wayfinder/prototype-ui.html` 的实际渲染就是每节点一对 in/out 圆点（标注「2 ports」的 memory 节点也只有两个点），`prototype-ui-interaction.md` 的表述（「小圆点，位于节点左右两侧」）亦可双向解读。即 §6.1 的选择与视觉基线一致，工程上可辩护，且单 Handle 在 React Flow 中是合法锚点。

**裁决**：**有条件接受该简化**，但必须满足两个条件：
1. 开工前取得用户对该偏差的**明确书面确认**（在 `wayfinder/grilling-decisions/issue-7-frontend-decisions.md` 中补一条 D10，或在 issue #7 下留言修订验收项为「port handle(s)」表述）；
2. PR 描述中显式声明此偏差及理由（原型实证 + 实现成本）。

---

### B3. 端口 5175 的决策没有落到实现步骤，文档自相矛盾

**实证链**：

- D1 定案 dev server 端口为 **5175**；§8.3 手动验证第 3 步访问 `http://localhost:5175`；
- 但 §5.2 脚手架步骤只配置了 `VITE_BACKEND_URL`，**从未要求在 `vite.config.ts` 中设置 `server.port = 5175`**。Vite 默认端口是 5173。

**后果**：按文档执行，dev server 起在 5173，§8.3 第 3 步直接失败，「dev server 一键启动」验收项的实际访问地址与 README/文档全部不符。

**修订要求**：§5.2 增加 `server.port`（及 `preview.port`）配置步骤；README 命令与之对齐。

---

### B4. 后端启动命令在仓库根目录无法执行

**实证链**（已实测）：

- 文档 §2.5/§8.3 与 `backend/README.md:23` 均写：
  ```bash
  python -m uvicorn backend.app:app --reload --port 8123
  ```
- 从仓库根目录执行该命令，Uvicorn 报错：`Could not import module "backend.app"`。
- 原因是后端包实际位于 `backend/backend/app.py`，从仓库根目录启动需用 `backend.backend.app:app`；或在 `backend/` 目录下执行原文命令。

**后果**：按文档「从仓库根目录执行」的说明，手动验证第一步就失败；agent 无法启动后端，前端无数据可测。

**修订要求**：
- 由于红线要求不编辑 `backend/` 内文件，设计文档 §2.5 与 §8.3 必须自己给出正确命令：`python -m uvicorn backend.backend.app:app --reload --port 8123`，并注释说明 README 命令的 cwd 前提。

---

### B5. Vite/React 版本决策与脚手架命令相互矛盾

**实证链**（已实测）：

- D5 定案「**Vite 6 + React 18 + TypeScript**」；
- §5.2 步骤 1 实际命令为 `npm create vite@latest frontend -- --template react-ts`；
- 当前 registry 输出为 Vite `^8.2.2`、React `^19.2.8`、React-DOM `^19.2.8`。

**后果**：决策记录失真；逐字执行的 agent 会得到一个与 D5 声称不符的依赖矩阵，污染后续所有依赖判断（如 `@xyflow/react` 兼容性、React 19 新行为）。

**修订要求**：二选一——
- ① 更新 D5 为「使用 create-vite 最新模板（当前输出 Vite 8 + React 19）」；
- ② 显式锁定版本，如 `npm create vite@6.0.0 frontend -- --template react-ts` 并手动降级 React 到 18。

---

## 三、重要问题（Major — 应修复，否则必然返工）

### M1. 轮询状态机缺失四类失败转移

§5.4 状态机只覆盖了 happy path，以下分支全部缺失：

| 场景 | 实证依据 | 现状 |
|---|---|---|
| 轮询请求本身网络失败 | 后端为内存 store；`backend/README.md` 明示 `--reload` 会重启进程并中断在途扫描 | 未定义：一次失败即 error，还是容忍 N 次？ |
| 轮询中收到 404 `job_not_found` | `app.py:77-78` 对未知 job 返回 404 | 未定义 |
| `status === done` 后 `getGraph` 失败（500/404/409 竞态） | `app.py:84-103` 三种失败码 | 状态机无此转移目标 |
| 扫描永不结束 | 无超时、无最大轮询时长、无用户取消入口 | interval 永远运行 |

**修订要求**：§5.4 补全状态转移图；定义超时/取消策略（哪怕只是客户端「放弃等待」按钮）；`setInterval` 建议改为 `setTimeout` 链式调用或加 in-flight 守卫，避免慢请求叠加。§8.2 需为 404 与 getGraph 失败各加一个 MSW 用例。

---

### M2. 同一模块对的多条依赖边完全重叠

**实证**：`parser/_edges.py` 对同一对模块可产出多条不同 `kind` 的边（`import` + `from_import` + `call` + `annotation`…）。在 B2 的单 source/单 target Handle 布局下，这些边几何上完全重合，`EdgeWithLabel` 的 label 也叠在一起——用户只能看到一条边，依赖关系被静默吞掉。

**修订要求**：§5.5 裁决其一——
- (a) 按 `(source, target)` 聚合为一条边（label 合并 kinds、Inspector 展示全部 sites，推荐，信息无损）；或
- (b) 平行边偏移。

§7 不变量清单应补一条「同模块对多边不重叠或已聚合」，§8.1 补对应测试。

---

### M3. 评分代理存在系统性偏差，阈值缺乏校准

`maxLine / portCount` 度量的是「最后一个公开符号所在的行号 ÷ 端口数」，而非真实 LOC。两类必然误判：

- 端口集中在文件头部的大文件：1000 行实现、端口全在前 50 行 → maxLine≈50，被系统性判浅；
- 小文件尾部恰好有一个端口：60 行文件、1 个端口在第 55 行 → ratio=55，被判深。

**缓解事实**：`schema.json` 已实证不含 LOC 字段，在不改后端的红线下客户端拿不到更优数据，接受 naive 合理（issue #7 亦明示「can be naive」）。

**修订要求**：
1. 用本仓库 `parser/` 包实跑一次扫描，把 `maxLine`/`portCount` 的真实分布贴进文档附录，按分布校准阈值；
2. `depthScore.ts` 代码注释中写明「naive、暂定、已知偏差场景」。

---

### M4. §2.2 真值表遗漏错误响应契约，§2.3 对 store 上限描述不精确

- §2.2 只记录了成功路径。已实证错误契约：`POST /api/scan` → 400 `invalid_json` / `invalid_request` / `path_not_found`；status/graph → 404 `job_not_found`；body 统一为 `{"error", "details"}`。§5.3 client「解析 `{error, details}`」方向正确，但真值表不补全，错误展示逻辑就没有契约依据，§7 不变量 5 也无法验证。
- §2.3 称「上限 100 个内存 job」：`store.py:66-78` 实证为——无可驱逐的 terminal job 时上限会被临时突破，create 不会失败。结论应写准为「前端无需处理扫描被拒绝」。

---

### M5. 空 Graph 边界未处理

若扫描结果 `modules` 为空数组，React Flow 将收到空 nodes/edges。需保证 UI 不崩溃，并显示「未解析到模块」提示。

**修订要求**：在 `App.tsx` 或 `graphToFlow.ts` 中对 `modules.length === 0` 增加显式分支。

---

### M6. 测试基建缺 setup 文件

§5.2 未列入 `src/test/setup.ts`（jest-dom 导入 + `msw/node` server 生命周期 + `onUnhandledRequest: 'error'`）。Q7 自问的 `import.meta.env` 问题不存在——Vitest 走 Vite 管线原生支持；真正的坑是 setup 缺失。

**修订要求**：§5.2 增加 `src/test/setup.ts` 创建步骤，并在 `vitest.config.ts` 中通过 `test.setupFiles` 引用。

---

### M7. 集成测试全部基于手写 mock

mock 写错测试照样绿。建议：用后端对 `parser/tests/fixtures/sample_pkg` 实跑一次，把**真实 Graph JSON** 存为前端测试 fixture，`graphToFlow`/渲染测试基于真数据——这一步顺带能提前暴露 B1。

---

### M8. `Inspector` 放置位置未明确

§5.7 写「点击节点/边：在右侧/底部 `Inspector` 显示详情」。「右侧/底部」二选一未裁决，agent 必须自己发明决策。

**修订要求**：明确选择一种布局（推荐右侧固定宽度面板），并在组件/文档中写明。

---

## 四、次要问题（Minor — 建议修复）

| # | 问题 | 说明 | 修订要求 |
|---|---|---|---|
| m1 | §2.6 变量名失真 | `#f87171` 在原型中名为 `--warn`（`.bad` 类引用 `var(--warn)`），文档记为 `--bad`。 | 前端自建变量可自由命名，但「代码真值」表应忠实于原型。 |
| m2 | 漏读 handoff 指定上下文 | handoff「Context pointers」要求先读 `wayfinder/design-data-schema.md` 与 `wayfinder/prototype-ui-interaction.md`，设计文档 §1 只列了 handoff 三节。 | 补引用或声明已读。 |
| m3 | §2.6 行号引用偏差 | 色板/节点/端口/边四处行号与原型实际位置略有出入。 | 按「全部可复现」标准复核。 |
| m4 | §8.3 手动验证带 `--reload` | `backend/README.md` 明示 reload 会中断在途扫描。 | 手动验证/演示长扫描时建议去掉 `--reload`，写进 README 与验证步骤。 |
| m5 | D1–D4 用户确认未归档 | 仓库 `wayfinder/grilling-decisions/` 下无 issue-7 决策归档文件。 | 实现后补充 `wayfinder/grilling-decisions/issue-7-frontend-decisions.md`，使后续 agent 可独立复核。 |
| m6 | §8.3 fixture 路径跨 worktree | 使用 master 工作树绝对路径，但实现应在当前 worktree 验证。 | 改为当前 worktree 相对路径，如 `parser/tests/fixtures/sample_pkg` 或 `backend/tests/fixtures/mini_pkg`。 |
| m7 | `vite.config.ts` 暴露 `VITE_BACKEND_URL` 表述误导 | Vite 自动暴露 `VITE_` 前缀环境变量，无需额外配置。 | 删除或改写该步骤。 |
| m8 | `npm install -D @types/node` 冗余 | Vite `react-ts` 模板已内置 `@types/node`。 | 从安装列表移除或标注可省略。 |
| m9 | `modules[].ports` 与顶层 `ports` 的字段差异未澄清 | `modules[].ports` 项不含 `moduleId`，顶层 `ports` 项含 `moduleId`。 | 在 §2.4 真值表中分两行写明，避免实现误读。 |
| m10 | Q6 `.gitignore` 虽非问题，但可留一行确认 | 嵌套 `.gitignore` 无冲突风险。 | 开工后 `git status --ignored` 核一下即可。 |

---

## 五、对 §9 评审焦点的统一裁决

| 问 | 合并裁决 | 理由 |
|---|---|---|
| Q1 把手语义 | **有条件接受简化** | 原型实证支持单对把手，但必须取得用户书面确认并修订 issue 验收项；否则按 per-port 实现，`edges[].targetPort` 字段已具备数据基础。 |
| Q2 行数代理 | **接受，须校准并注释** | 无更优客户端数据（schema 无 LOC 已实证），但须按 M3 用真实分布校准并写明已知偏差。 |
| Q3 阈值 50/15 | **暂不可用，须校准后回填** | 当前为无数据支撑值；注释标「暂定」是最低要求，贴分布数据是充分要求。 |
| Q4 布局 | **同意先网格** | 但 §5.5 须定义网格间距常量（相对 160px 节点宽 + 水平/垂直间距），dagre 留后续 issue 跟踪。 |
| Q5 CORS | **同意不改后端** | `["*"]` 默认属实已实证；按 m4 在 README 加一句「收紧环境用 `BACKEND_CORS_ORIGINS` 覆盖」即可。 |
| Q6 `.gitignore` | **非问题** | 见 m10。 |
| Q7 测试环境 | **方向错了** | `import.meta.env` 在 Vitest 下不是问题；要补的是 setup 文件（M6）。 |

---

## 六、文档优点（应予保留，修订时勿破坏）

1. **溯源纪律真实可靠**：抽查的十余处 `file:line` 与行为声明全部属实，未发现伪造溯源或把判断伪装成事实；
2. **§4 范围收敛 + §7 不变量清单**是防止实现阶段漂移的正确机制，建议 B1/M2/M8 的修订也以不变量形式沉淀；
3. **§9 主动暴露疑点**的姿态正确——Q1/Q2 恰好问中了本次审计确认的真问题；
4. worktree 纪律、红线（不动后端、不做自定义画布/AI 功能、敏感操作需授权）与 handoff 完全对齐；
5. 真值表格式、决策记录格式、证据来源标注均符合项目可审计要求。

---

## 七、修订验收清单（供 §10 回填与复审）

复审时逐项核对：

- [ ] **B1**：`externalModules` 渲染/过滤策略已裁决并写入 §5.5，测试与布局连带修订；
- [ ] **B2**：把手简化获用户书面确认（新决策记录或 issue 留言），PR 模板含偏差声明；
- [ ] **B3**：`vite.config.ts` 端口 5175 配置进入 §5.2 步骤；
- [ ] **B4**：§2.5/§8.3 给出从仓库根目录可实际运行的后端启动命令；
- [ ] **B5**：脚手架命令钉版本或修订 D5，二者一致；
- [ ] **M1**：状态机补全四类失败转移 + 超时/取消策略，§8.2 补两个 MSW 用例；
- [ ] **M2**：同模块对多边聚合/偏移裁决 + 不变量 + 测试；
- [ ] **M3**：真实分布数据附录 + 阈值校准 + 代码注释要求；
- [ ] **M4**：§2.2 补错误契约（400/404/409/500 及 `{error,details}` 形状），§2.3 措辞修正；
- [ ] **M5**：空 Graph 边界处理；
- [ ] **M6**：`src/test/setup.ts` + `vitest.config.ts` 配置；
- [ ] **M7**：真实 Graph JSON fixture 进入测试；
- [ ] **M8**：`Inspector` 布局明确为右侧或底部；
- [ ] **m1–m10**：按上表落地。

**复审触发条件**：上述清单全部回填后，复审只查增量，不重审全文。

---

## 八、证据基线（本次合并审计独立实证记录）

| 文档声明 | 实证来源 | 结果 |
|---|---|---|
| issue #7 open、无标签/assignee、被 #5 阻塞 | GitHub issue #7 | ✅ 属实 |
| §2.2 三端点行为、CORS 默认 `["*"]` 可环境变量覆盖 | `backend/backend/app.py` 全文 | ✅ 属实；另实证 400/404/409/500 错误形状为 `{"error","details"}` |
| §2.3 JobStatus/Job 字段/100 上限/仅驱逐 terminal | `backend/backend/store.py` 全文 | ✅ 基本属实；上限可被临时突破的细节不精确 |
| §2.4 Schema 五键结构、edges/externalModules/diagnostics 形状 | `parser/schema.json` 全文 | ✅ 属实；schema 无 LOC 字段（M3 关键依据）；`edges[].targetPort` 存在（B2 备用论据） |
| 第三方依赖会产生指向 `modules` 之外的边 | `parser/_edges.py`、`parser/_external.py`、实跑 `sample_pkg` | ⚠️ **实证成立，文档盲区 → B1** |
| handoff 锁定轮询、2 秒间隔、把手 per-port、红线四条 | `wayfinder/handoff-build-frontend-real-view.md` 全文 | ✅ 属实；B2 冲突来源 |
| §2.6 色板与节点/端口/边样式 | `wayfinder/prototype-ui.html` 全文 | ✅ 色值与尺寸属实；变量名 `--warn` 被记为 `--bad`（m1）；原型实证为单对 in/out 把手（B2 缓解事实） |
| §2.5 后端启动命令 | `backend/README.md` + 实测 | ❌ **从仓库根目录执行失败 → B4** |
| D5 Vite 6 + React 18 | `npm create vite@latest` 实测 | ❌ **实际输出 Vite 8 + React 19 → B5** |
| §2.1 `frontend/` 不存在、git 分支/工作树状态、Node 版本 | 本地环境 | ✅ 属实 |
| `@xyflow/react` peerDependencies | `npm view @xyflow/react peerDependencies` | ✅ 支持 React ≥17，React 19 可用 |

---

## 九、结语

本设计文档的方向、范围与架构纪律经得住复核，两份独立评审均未发现证据造假或重大架构错误。真正的风险集中在三类「最后一公里」问题：

1. **可直接执行的句子与真实环境不符**（B3/B4/B5）；
2. **真实数据灌入后会暴露的边界盲区**（B1/M1/M2/M3/M5）；
3. **与书面验收标准的程序性偏差**（B2）。

建议以 §七 清单作为修订与 PR 自检表，全部回填后触发一次轻量复审即可进入实现。

—— 合并审计方（评审意见书 + 下载审计报告综合，2026-08-26）
