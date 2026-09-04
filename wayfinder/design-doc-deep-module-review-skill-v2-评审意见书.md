> **评审对象**：《迁移 deep-module-mapper 为 Claude Code skill `/deep-module-review` —— 设计文档（供评审）》**v2 章节（§11–§18）**——Archify 模块地图 + 模块内下钻
> **评审方式**：以本地仓库 `C:/Users/liyongquan/agent panel/deep-module-mapper/` @ `ddb4562`（分支 `feature/deep-module-review-skill` HEAD，`git log --oneline -1` 实测确认）为真值源，逐项实测与 grep 复核；原型产物实测于 `%TEMP%\dmm_v2_demo\`；Archify 约束实测于 `~/.claude/skills/archify/`；GitHub issue #24 v2 区块比对一致。
> **评审结论**：**有条件通过**（无阻塞级发现；F1–F5 五项重要问题须在实现前补进设计或以带测试的方式落实）

---

## 一、总体结论

v2 方向有扎实的实证底座，这在设计文档里不多见：核心事实（模块内调用被 parser 主动丢弃、archify 静态交付、原型验收）全部实测复核为真，行号引用精确到行（`_edges.py:79`、`_edges.py:307-308`、`_schema.py:108` 全部逐行命中）。原型不是纸面推演——评审方独立重跑 `archify validate architecture dmm.architecture.json --quality showcase` 得 ok=true、9 项检查全过、零诊断；`deliver workflow w_edges.json` 得 checksPassed 9/9，§13.3 的主张可独立复现。原型教训（§13.4-2 的 id 正则 bug）有真凭实据：`build_prototype.py:197` 已改为 `(?<=\s)id="..."`，实测 `prototype.html` 主图 `data-node-id` 为裸短名且与 `panel-*` 一一对应、`id=` 全部带前缀未被误伤。

但设计文本有四类问题必须在动 parser 之前解决：
1. **V2-D9 与既有测试正面冲突**：`parser/tests/test_scan_codebase.py:22` 有精确 5 键断言，新增第 6 键 `intra` 必炸此测试，"既有 39 parser 测试不回归"（§16.4）按字面不可能成立；兼容面清点还漏了 `schema.json` 的 `additionalProperties: false` 与 README/SKILL.md 的书面"5 顶层键"契约。
2. **函数级捕获的误报风险无策略**：回调引用（边③）与属性调用在同名遮蔽场景下会产生幻边，现有 `locals_` 机制不是作用域敏感的，设计未提消歧，验证计划无对应测试。
3. **模块 id → archify 节点 id 的映射没有设计**：真实模块 id（`parser/_edges.py`）不满足 archify id pattern，sanitize 会碰撞，碰撞即静默错联——§13.4-2 事故的同类变体；原型里这一步是手写映射，恰恰说明它不是免费的。
4. **"确定性布局"措辞与随机重启爬山兜底自相矛盾**，Q5 只提问未裁决；且 V2-D10 降级路径在验证计划里零覆盖。

总体评价：事实链与原型验收是 v2 最强的部分；薄弱处在"从原型到通用实现"的落地规则（id 映射、误报消歧、确定性、降级）。补齐后可执行。

---

## 二、事实与证据复核

### 2.1 核实为真

| 计划主张 | 复核结果 |
|---|---|
| §13.1 `graph.json` 80 条边中 call 类 40 条全部跨模块、模块内 0 条 | ✅ 实测 `.last-review/graph.json`：总边 80（from_import 30 / call 40 / annotation 5 / import 3 / inheritance 1 / decorator 1），call 40 条 source≠target 40、source==target 0。 |
| §13.1 `_edges.py:79` 已遍历 FunctionDef | ✅ `_edges.py:79` 逐字命中 `elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):`。 |
| §13.1 `resolve_reference` 对本地名直接跳过，约在 307-308 行 | ✅ `_edges.py:307-308` 精确命中：`if name in module_defs or name in locals_: return Resolution()  # module-internal reference, not a cross-module edge`。行号无偏差。 |
| §13.4-1 `_schema.py:108` `sorted(key=_edge_sort_key)` 是回调引用不是调用 | ✅ `_schema.py:108` 逐字命中；`_edge_sort_key` 以 Name 出现在实参位置、从不被 Call——"只抓 Call 会漏"的论据成立。 |
| §14 前置：`Graph.to_dict` 现返回 5 键 | ✅ `_schema.py:102-111`，键序 modules/ports/edges/externalModules/diagnostics。 |
| parser 测试基线 39 passed | ✅ 实测 2026-09-05：`python -m pytest parser/tests -q` → `39 passed in 0.15s`。skill 测试亦实测：13 passed。 |
| §13.3 `intra.json` 7 模块 42 函数 | ✅ 实测逐模块 funcs 数 1/7/3/15/8/2/6，合计 42，模块为 parser 7 个生产文件；结构与设计形状不同但调用数据真实（如 `collect_references → _add_ref`）。 |
| §13.3 7 张 `w_*.json` + `dmm.architecture.json` 存在 | ✅ 7 张 workflow IR 齐全，`schema_version` 全为 2，col 全部 ≤5；主图 IR 存在（`schema_version` 1，region 边界包裹 7 组件）。 |
| §13.3 `prototype.html` 约 271KB 单文件 | ✅ 存在，实测 290,696 字节（≈284KB）——与"271KB"差约 5%，文件于 09-05 03:37 重新生成过，量级主张成立（备注级偏差）。 |
| §13.4-2 `unique_ids` 已改 `(?<=\s)id="..."`；主图 `data-node-id` 裸短名与 `panel-*` 一一对应 | ✅ `build_prototype.py:195-205` 命中；实测 prototype.html：主图 `data-node-id` = main/diagnostics/edges/external/ports/scanner/schema，7 个 `panel-<同名>` 全对应，arch svg 内 `id=` 全部已改写为 `arch-*`、`data-node-id` 未被误伤。 |
| §13.2 组件 schema 无 click/link/href 字段 | ✅ `schemas/architecture.schema.json`、`workflow.schema.json`、`common.schema.json` 全文 grep click/href/link 均无命中。 |
| §13.2 node id pattern `^[a-zA-Z][a-zA-Z0-9_-]*$` | ✅ `common.schema.json#/$defs/id` 逐字命中（architecture 与 workflow 的节点 id 共用该定义）。 |
| §13.2 workflow `col ≤ 5` | ✅ `workflow.schema.json` nodes.items.col：`{"type":"integer","minimum":0,"maximum":5}`。 |
| §13.2 workflow `schema_version=2` | ⚠️ 基本属实但措辞不准：schema 实为 `enum:[1,2]`（examples 里 1、2 都有）；原型 7 张 IR 全用 2。按"原型所用版本"理解成立，按"schema 规定为 2"理解不准确。 |
| §13.2 渲染器无事件监听（交付静态页） | ✅ `renderers/` 全目录 grep `addEventListener|onclick|onClick` 零命中。 |
| §13.2 节点组自带 `data-node-id`/`role="button"`/`tabindex` | ✅ `renderers/shared/cli.mjs:200`：`id="node-…" data-node-id="…" tabindex="0" role="button" aria-pressed="false"`。 |
| §13.2 交付命令形态 | ✅ `bin/archify.mjs` usage：`archify deliver <type> <input.json> [output.html] [--json] [--open] [--quality standard|showcase]`。 |
| §13.2 同泳道同列节点 <8px 间距报错 | ✅ `renderers/shared/geometry.mjs:1416` `suggestComponentSeparation(a, b, minGap = 8)`。 |
| §13.2 中文经 GBK 控制台需 `subprocess(encoding="utf-8", errors="replace")` | ✅ `build_prototype.py:168`、`hillclimb.py:35` 均如此实现（Windows 实操教训）。 |
| §13.3 主图 showcase 9/9、零诊断布局 | ✅ **评审方独立复跑**：`archify validate architecture dmm.architecture.json --quality showcase --json` → ok=true，9 项检查（single_svg…legend_clearance）全过，diagnostics 为空；`deliver workflow w_edges.json` → checksPassed 9/9。"手工布局十余次卡几何交叉"有 try*.py×4、try2/try3、v_std.json、validate_out.json 等 8 个试错产物佐证（精确次数不可复核）。 |
| §12 主图口径 = `metrics.py::is_production_module`；本仓库 7 个生产模块 | ✅ `metrics.py:70-72` 存在；实测 metrics.json 恰 7 个生产模块，与 intra.json 7 模块、原型 7 面板三方一致。 |
| §12 卡片副标签/tag 规则 | ✅ 与 `hillclimb.py:18-21` 一致：shallow → `浅`，fanOut≥5 → `扇出偏高`。 |
| 事实 11：v1 降级路径素材存在 | ✅ `scripts/` 五文件齐；`analyze.py:81,95,100` 产 `diagram.svg`（`diagram.build_svg`）；`template.html` 在；v1 全流程产物（review-*.html）在。 |
| §11 v1 已实现、工作区干净 | ✅ HEAD `ddb4562` 即设计文档提交；`git status` 无未提交的代码改动。 |
| issue #24 v2 区块与文档一致 | ✅ `gh issue view 24` 的 v2 区块（方向 / V2-D1~D10 / 原型验收 / 待实现四项）与 §11–§15、decisions 文件 v2 节相互一致。 |
| V2-D10 的 `~` 展开在本机无坑 | ✅ 实测本机 `HOME`=`USERPROFILE`=`C:\Users\liyongquan`，`Path.home()` 正确解析（通用性备注见 F5）。 |

### 2.2 不实 / 冲突

| 项 | 说明 |
|---|---|
| **§16.4"既有 39 parser 测试不回归"与 V2-D9 直接冲突** | `parser/tests/test_scan_codebase.py:22`：`assert set(graph.keys()) == {"modules", "ports", "edges", "externalModules", "diagnostics"}`。新增第 6 键后此断言**必然失败**——除非修改该测试。设计全文未提此事；"39 测试不回归"若按"不改一行全绿"理解则与新键互斥。这是实锤的文档内部矛盾，不是风险推测。 |
| §11 / decisions："16 项 grilling" | decisions v2 节实际逐条列出 **17** 项（多项目通用 … 单入口分模式）。差 1，无法判定哪项多列；因全部已搁置，影响为零，但计数失实。 |
| §16.2"既有 5 键契约**逐字节**兼容" | 措辞过强：该主张成立的前提是扩展实现为纯附加 pass（不动 `resolve_reference` 既有行为），且当前没有任何 golden 测试能验证"逐字节"；同时 `parser/schema.json` 顶层 `additionalProperties: false`——schema 不同步则产物 schema-invalid（文档提了同步，但没提 `required` 里 `intra` 去留）。见 F1。 |

### 2.3 不可复核

| 项 | 说明 |
|---|---|
| 用户四条原话引用（"我不需要这么多数据和趋势""点开模块之后…""对，就是这个效果"等）及各日期 | 对话内容无法从仓库复核；decisions 文件已落档且与文档一致，采信落档。 |
| "手工布局十余次"的精确次数 | 试错产物（8 个文件）佐证"多次"，次数本身不可复核。 |
| `dmm.html`（§11 称 09-04 打通）文件 mtime 为 09-03 17:50 | 以产物存在为准，具体哪天打通不作裁决。 |

---

## 三、逐条评审

| 决策/章节 | 结论 | 评审意见 |
|---|---|---|
| V2-D1 产出 = Archify 式架构图，数据面板废弃 | **认可** | 用户否决原话在案，方向转向有据。AI 结论降级为图下一段+面板解读，符合"只要图表"的诉求。 |
| V2-D2 以 v1 分支为基线 | **认可** | 实测 v1 五脚本+13 测试全在，基线真实。 |
| V2-D3/V2-D4 真实调用图为底 + AI 泳道标注 | **认可（附条件）** | "不采用纯 AI 解读（不可溯源）"的理由成立。条件：误报消歧策略必须先定（F2），否则"真实"二字打折扣。 |
| V2-D5 单文件 HTML 同页内嵌面板 | **认可** | 原型已验收，点击映射实测无失配。交付形态遗留问题见 F7。 |
| V2-D6 函数级、类=单节点 | **认可（附条件）** | 粒度选择合理（方法级图会爆炸）。条件：归属规则补全（嵌套 def/lambda/条件内 def/重名，F6）。"类方法体内调用记为类节点出边"可用 scope 栈实现，可实现性无问题。 |
| V2-D7 面板内容四件套 | **认可** | "函数级无环时如实说明循环发生在文件级迭代"的诚实呈现（§13.4-3）是好设计，原型已验证此路径。 |
| V2-D8 原型验收冻结形态 | **认可** | 验收不是口头的：评审方独立复跑 validate/deliver 均过，原型产物链完整。 |
| V2-D9 第 6 键 `intra` | **认可（附条件）** | "一次扫描一处产出"的理由成立，独立文件方案确会割裂 graph.json 语义。但兼容面清点不全且有实锤冲突（test:22 / schema.json `additionalProperties:false` 与 `required` / README+SKILL.md 书面 5 键契约），"逐字节"措辞无测试兜底。见 F1。 |
| V2-D10 archify 可选 + 降级 v1 SVG | **认可（附条件）** | "不能硬依赖另一个 skill"的理由成立；探测顺序（`ARCHIFY_DIR` → `~/.claude/skills/archify`）在本机实测可行。条件：降级路径零验证覆盖、降级产物形态未写明、探测不查 node 运行时。见 F5。 |
| §14 `intra` 覆盖含 tests/ 的全部文件 | **认可** | "裁剪是 metrics 层职责、parser 不裁"延续现有分层（digest/metrics 已有 is_noise_module 先例），站得住。规模代价见 F7。 |
| §14 性能主张 | **基本认可** | 单文件粒度 O(几十)函数成立；`ast.walk` 为迭代实现，"无递归深度风险"正确。总仓库规模乘数未提（F7 附带）。 |
| §15 管线（to_archify → archify deliver ×N → assemble） | **认可（附条件）** | 分工清晰、红线（只读、产物全落 `.last-review/`）保留。条件：id 映射设计缺失（F3）、"确定性"矛盾（F4）、panels/ 产物契约只有一句话（模块 id 含 `/` 和前导 `_`，panels/ 文件命名、node id 生成规则、约束校验归属均未定义——目前仅"SKILL.md 增补产出规范"一句，不足以直接执行）。 |
| §15 assemble.py 的 svg 摘取/样式合并 | **认可（实测后放心大半）** | 实测当前 archify 各 deliver 的 `<style>` 块**字节级一致**且 style 内无 `#元素id` 选择器（命中的 140 个 `#xxx` 全是色值）——原型 set 去重成立、id 前缀改写不破坏样式；`single_svg` 校验保证每 deliver 恰一个 svg 块。剩余兜底问题见 F8。aria id 冲突已由 unique_ids 对 id=/url(#)/href(#)/aria-labelledby 四类改写覆盖（原型实测有效）。 |
| §16 不变量 1/3/5 | **认可** | 只读、parser 零第三方依赖（archify 为进程调用非 import，措辞准确限定 parser）、指标口径不变——逐条成立。 |
| §16 不变量 2 | **不认可（按现措辞）** | "逐字节兼容"见 2.2 冲突表；应改写为"5 键内容不变 + golden 断言 + schema 同步"，见 F1。 |
| §16 不变量 4 | **不成立（按现措辞）** | 与 test:22 冲突，见 2.2。 |
| §17 验证计划 | **方向认可、覆盖不足** | 三层（parser 单测 / skill 单测 / e2e）骨架对，id 映射一致性测试（防 §13.4-2 复发）打在要害上。但缺：降级路径测试（F5）、shadowing 场景（F2）、id 碰撞检测（F3）、5 键不变 golden 断言（F1）。 |
| §18 Q3–Q5 | **开放点选得部分对，漏了更危险的** | Q3/Q4/Q5 均是真问题，但 Q4 的已知消费方清单不全（F1 实证）；更危险的三个开放点没列：模块 id→archify id 映射（F3）、误报消歧（F2）、map.html 交付形态（F7）。 |

---

## 四、开放点裁决（对 §18 Q3–Q5 的评审方意见）

### Q3 archify 缺失降级 v1 SVG 是否可接受 —— **裁决：可接受，但降级契约要写死**

可选依赖 + 降级是正确取舍（skill 要多项目通用）。但设计必须补三件事：① 降级产物形态 = v1 四件套 + template.html Artifact 全流程，还是仅 diagram.svg？现文含糊；② 明示机制落在哪（stdout JSON 加字段 / SKILL.md 协议步骤），避免"明示"沦为口头；③ 探测通过但 `node` 不可用（archify 目录在、node 没装）时按降级处理——现探测只查目录。

### Q4 `intra` 第 6 键是否破坏其他消费方 —— **裁决：同仓库内全部可同步改，但清单必须补全后再下此结论**

"已知消费方：analyze.py、metrics.py、digest.py"不全。实测完整清单：`parser/tests/test_scan_codebase.py:22`（**必炸**）、`parser/schema.json`（`additionalProperties:false`，不同步即 schema-invalid；`required` 需决定 `intra` 去留）、`README.md:31` 与 `SKILL.md:35`（书面"5 顶层键"契约）、`.claude/skills/deep-module-review/tests/test_skill.py`（手工构造 5 键假图喂 metrics/digest——用 `.get()` 读取，功能不受影响，但 fixture 需决定是否补 `intra`）。结论不变（都在同仓库），但 Q4 现有论据不完整。

### Q5 布局"确定性优先、搜索兜底"的边界 —— **裁决：必须裁决，不能留作开放点**

见 F4。三条硬要求：兜底搜索固定 seed（或记录最终布局进 `.last-review/` 供复用，即 Q5 后半句的方案，评审方支持）；几何校验进程内实现（原型每候选 spawn 一次 node 子进程的做法不可进生产）；"确定性生成"的措辞改为"确定性 IR + 确定性优先布局 + 可复现兜底"。

---

## 五、新发现问题

| # | 级别 | 问题 | 证据 | 修复建议 |
|---|---|---|---|---|
| F1 | **重要** | V2-D9 兼容面清点不全，且与既有测试正面冲突：`test_scan_codebase.py:22` 精确 5 键断言加键必炸；`parser/schema.json` 顶层 `additionalProperties: false`（schema 不同步则产物 schema-invalid）且 `required` 中 `intra` 去留未定；`README.md:31`、`SKILL.md:35` 书面"5 顶层键"契约需同步；"逐字节兼容"无 golden 测试兜底。 | `parser/tests/test_scan_codebase.py:22`；`parser/schema.json`（additionalProperties=false，properties 无 intra）；`README.md:31`；`SKILL.md:35` | §14/§16 补写：同步修改 test:22（改为"5 键内容不变 + 允许 intra"或 golden 断言）；schema.json 加 `intra` properties 并明确是否入 required；README/SKILL.md 键数表述更新；新增"扩展前后 5 键输出逐字节一致"的 golden 单测。 |
| F2 | **重要** | 回调引用（边③）与属性调用捕获无同名遮蔽消歧策略：现有 `locals_` 是全模块所有函数参数/赋值名的**并集**（非作用域敏感），局部变量/参数与模块级函数同名即产生幻边；原型的 Attribute 捕获（`obj.method` → attr 命中本模块 def 名，`extract_intra.py:25`）同理（如模块恰有 `def write_text` 则 `out.write_text(...)` 成幻边）。幻边会作为"真实调用"呈现在评审图上，直接误导评审结论。§17 无 shadowing 测试场景。 | `parser/_edges.py:134-147`（collect_local_names 全函数并集）；`%TEMP%\dmm_v2_demo\extract_intra.py:24-26` | §14 增补消歧规则：边③要求该 Name 在引用点作用域内**未被绑定**（至少排除被赋值/作参数的同名命中）；明确属性调用是否入边（建议：纯 Name 调用 + Name 实参引用，属性调用不入，宁缺勿幻）；§17 补 shadowing 场景单测。 |
| F3 | **重要** | 模块 id → archify 节点 id 的映射没有设计：生产模块 id 形如 `parser/_edges.py`（含 `/`、`.`、前导 `_`），不满足 archify id pattern；sanitize 后可碰撞（`parser/_edges.py` 与假想 `parser/edges.py` 同映射为 edges），碰撞即面板错位/点击错联——§13.4-2 同类事故的变体且更隐蔽。原型此步是**手写** SHORT 字典，恰证明它不是免费的。 | `common.schema.json#/$defs/id`（pattern 禁 `/` `.` 与前导 `_`）；`hillclimb.py:5-8`（手写 SHORT 映射）；`build_prototype.py:144`（`re.sub(r"^_+","",fname)`） | §15 补映射规则：确定性 id 生成（如路径段拼接 `parser__edges`）+ 生成后查重断言（碰撞即报错不静默）+ 模块完整 id 存入节点 sublabel/映射表；§17.2 补碰撞检测测试。 |
| F4 | **重要** | 主图布局"确定性生成"（§15）与随机重启爬山兜底矛盾未裁决：原型 hillclimb.py 实为 `random.seed(42)` × 60 次重启搜索，且**每个候选布局 spawn 一次 `node archify.mjs validate` 子进程**（7 节点尚可，节点多的目标仓库不可行）。Q5 只提问未裁决；同仓库两次运行图样不同，损害前后对比的评审体验。 | `hillclimb.py:43`（random.seed(42)）、`:47`（60 restarts）、`:34-38`（每候选一次 subprocess） | §15 落裁决：兜底搜索固定 seed + 布局结果缓存进 `.last-review/layout.json`（Q5 后半句方案，采纳）；几何交叉校验改为进程内实现（archify 的重叠判据 minGap=8 可自实现），仅对最终布局跑一次 archify validate 确认。 |
| F5 | **重要** | V2-D10 降级路径零验证覆盖、契约不清：§17 无任何"archify 缺失 → 降级"测试项；降级产物形态未写明（v1 四件套+template Artifact 还是仅 diagram.svg）；探测只查目录存在，不查 `node` 运行时可用（目录在而 node 缺失会走"探测成功→子进程失败"未定义路径）。 | `wayfinder/design-doc-deep-module-review-skill.md` §17（三条验证项均与降级无关）；`bin/archify.mjs` 依赖 node 运行时 | §15 写死降级契约（产物清单+明示字段）；§17 增加两条：模拟 `ARCHIFY_DIR` 指向空目录 + `~/.claude/skills/archify` 不存在时的降级 e2e；探测序列补 `node --version` 探测，失败按降级处理。 |
| F6 | **建议** | §14 归属规则缺口：嵌套 def、lambda、条件分支内的 def（不在 `tree.body` 直属层）、同名重定义（calls 按 name 引用即歧义）均未定义归属；§14 边②要求"模块顶层语句中的调用"入图，但原型实现把顶层调用整体丢弃（`extract_intra.py:30` `del funcs["<顶层>"]`），实现者照抄原型会静默漏掉边②。 | `extract_intra.py:10,30`；§14 节点/边定义 | §14 补一段归属表：嵌套 def 是否独立节点（建议：并入其宿主节点）、lambda 内调用归属宿主、条件内 def 按 walk 收录、同名重定义按首个定义或报错；明确设计形状（funcs 数组 + calls 数组）与原型形状（嵌套 dict）不同，单测按设计形状写。 |
| F7 | **建议** | 交付形态与规模上限未讨论：v1 契约是 HTML Artifact（D3），v2 `map.html` 实为浏览器文件（§17"浏览器打开"），设计未明说这一转变，实现时按 v1 习惯塞 Artifact 可能超限（本仓库 7 面板已 290KB，大仓库多面板会到 MB 级）；`intra` 覆盖含 tests/ 的全部文件使 graph.json 随仓库规模膨胀明显。 | §12（产出=map.html）；§17.3（浏览器打开）；实测 prototype.html 290,696 字节 | §12 加一句交付方式裁决（建议：写文件+提示用户浏览器打开，不进 Artifact）；规模策略可留 TODO 但应记录（如超阈值时只对 deep/moderate 模块生成面板）。 |
| F8 | **建议** | assemble.py 样式合并缺兜底约定：实测当前 archify 各 deliver 的 `<style>` 块字节级一致、style 内无 `#元素id` 选择器（仅色值），set 去重与 id 前缀改写安全；但设计未写"样式块不一致时"的策略，archify 升级若分化样式或引入 id 选择器，该假设静默失效。GBK 子进程编码处理（§13.2 教训）也值得固化为单测。 | 实测 dmm.html 与 w_edges.html `<style>` 块 `==` 为 True；style 内 `#` 命中均为色值 | assemble.py：样式块不一致时全部拼接（后写覆盖先写）并加注释说明前提；skill 单测加一条：subprocess 包装器以 `encoding="utf-8", errors="replace"` 调用（防回归 §13.2 教训）。 |

---

## 六、通过条件清单（实现前勾选）

- [ ] **F1**：§14/§16 增补 test_scan_codebase.py:22 的同步修改说明；schema.json 的 `intra` properties 与 `required` 去留定案；README/SKILL.md 键数表述列入改动清单；5 键 golden 单测入 §17。
- [ ] **F2**：§14 增补同名遮蔽消歧规则与属性调用取舍；§17 补 shadowing 场景单测。
- [ ] **F3**：§15 增补模块 id → archify id 的确定性映射规则 + 碰撞断言；§17 补碰撞测试。
- [ ] **F4**：Q5 落裁决（固定 seed / 布局缓存 / 进程内几何校验），§15"确定性"措辞修正。
- [ ] **F5**：V2-D10 降级契约写死（产物形态 + 明示机制 + node 探测）；§17 补降级 e2e 两例。
- [ ] **F6**（建议）：§14 归属表补全（嵌套/lambda/条件 def/重名/顶层调用）。
- [ ] **F7**（建议）：§12 明确 map.html 交付方式。
- [ ] **F8**（建议）：assemble.py 样式兜底与 subprocess 编码单测。
- [ ] 实现完成后：parser 测试全绿（含更新后的键断言与新增单测）、skill 单测全绿、e2e 对本仓库产出 map.html 且 7 面板函数/边数与 `intra` 一致、降级路径人工触发一次。

---

## 七、结语

v2 设计的事实层是同类文档里的优等生：行号级引用零误差，原型可独立复现（评审方重跑 validate/deliver 均过），§13.4 的三条原型教训全部有产物实据。问题集中在"原型经验 → 通用实现"的规则缺口：id 映射、误报消歧、确定性、降级契约，以及一处实锤的内部矛盾（第 6 键 vs 精确 5 键测试断言）。五项重要发现全部可在设计文本内修复，不需要推翻任何已验收的形态决策。建议按 §六 清单补齐后进入实现；实现顺序上，parser 扩展（§14）应最后动——它是唯一影响既有契约的改动，前置 golden 测试先落。

—— 评审方（独立复核：本地仓库 @ ddb4562，2026-09-05）

---

## 附录：执行检查表（评审实测记录）

| 类别 | 检查项 | 状态 | 备注 |
|---|---|---|---|
| git | HEAD = `ddb4562` @ `feature/deep-module-review-skill` | ✅ | `git log --oneline -1` 命中 |
| 数据 | graph.json 80 边 / call 40 全跨模块 / 模块内 0 | ✅ | Python 实测计数 |
| 代码 | `_edges.py:79` / `:307-308` / `_schema.py:108` | ✅ | 行号全部精确命中 |
| 命令 | `python -m pytest parser/tests -q` | ✅ | 39 passed (0.15s) |
| 命令 | `python -m pytest .claude/skills/deep-module-review/tests -q` | ✅ | 13 passed（v2 未动基线） |
| 数据 | intra.json 7 模块 42 函数 | ✅ | 1+7+3+15+8+2+6=42 |
| 文件 | w_*.json ×7（schema_version=2，col≤5）+ dmm.architecture.json + prototype.html | ✅ | prototype.html 290,696 B |
| 代码 | build_prototype.py:197 `(?<=\s)id="..."` | ✅ | §13.4-2 修复在案 |
| 数据 | prototype.html data-node-id（裸短名）↔ panel-* 一一对应 | ✅ | 7/7 对应；arch svg id 已全部加前缀 |
| schema | archify id pattern / col≤5 / 无 click·href·link / workflow enum[1,2] | ✅/⚠️ | enum[1,2] 与"=2"措辞有出入（轻微） |
| 代码 | renderers 无事件监听；cli.mjs:200 data-node-id/role/tabindex | ✅ | 静态页主张成立 |
| 命令 | `archify validate architecture … showcase` | ✅ | **独立复跑** ok=true、9/9、零诊断 |
| 命令 | `archify deliver workflow … standard` | ✅ | **独立复跑** checksPassed 9/9 |
| 数据 | metrics.json 生产模块 7 个 ≡ intra 7 ≡ 面板 7 | ✅ | 三方一致 |
| 代码 | metrics.py:70 is_production_module；analyze.py 产 diagram.svg | ✅ | v1 降级素材齐 |
| 冲突 | test_scan_codebase.py:22 精确 5 键断言 vs 第 6 键 | ❌ | 实锤，见 F1 |
| 冲突 | "16 项 grilling" vs 列举 17 项 | ❌ | 轻微计数失实 |
| 数据 | 各 deliver `<style>` 块字节级一致、无 #id 选择器 | ✅ | assemble 去重前提当前成立（F8 兜底） |
| 代码 | hillclimb.py random.seed(42)×60 重启、每候选一次 subprocess | ❌ | 与"确定性"措辞冲突，见 F4 |
| GitHub | issue #24 v2 区块 | ✅ | 与 §11–§15、decisions v2 节一致 |
