# #3 Implement Python AST parser — 设计评审意见书（v2，两份评审合并版）

> **评审对象**：《#3 Implement Python AST parser — 设计文档（供评审）》（v2，含 §2.4、D14–D16、§6.5–6.7、不变量 11–13、Q7–Q9）
> **评审方式**：合并两份独立评审 —— 本意见书（首轮，本地仓库 @ `f216e26` + gh CLI + Python 3.13.11 实测）+ 复审报告《Implement Python AST parser 设计文档 v2（第二轮）》；复审报告独有的主张我已逐项复核，未复核项均标注。全部可验证事实均以仓库/GitHub/Python 实测为真值源。
> **评审结论**：**有条件通过**（阻塞项 3 个，全部为低成本一次性修复）

---

## 〇、两份评审的对照（为什么"不太一样"）

| 主题 | 本意见书 | 复审报告 | 结论 |
|---|---|---|---|
| 顶层键矛盾（ports 4 vs 5） | F1 | P0-1 | **独立命中同一缺陷** ✅ |
| 解析失败隔离 / parse_error | F5 | P0-2 | 独立命中 ✅ |
| 目录排除（venv 噪音） | F6 | P0-3 | 独立命中 ✅ |
| 未解析符号判定 / builtins / 作用域 | F3 | P0-4 | 独立命中，方向一致；复审更强调作用域链与 `self.x()`，我更强调 builtins 误报 ✅ |
| 标准库"由实现定" | F7 | P1-2 | 独立命中 ✅ |
| requires-python 声明 | S6 | P1-4 | 独立命中 ✅ |
| `/tmp` 路径 Windows 不可用 | S4 | P2-4 | 独立命中 ✅ |
| dict 字段契约未钉死 | F8 | Q7 | 独立命中；复审建议用 JSON Schema 作唯一真源，更强，采纳 |
| dict vs 包装对象 | Q8 裁决 | Q8 裁决 | 一致（否决包装类）✅ |
| `_scanner` 拆分触发器 | Q9 裁决 | Q9 裁决 | 一致方向；复审要求量化触发器（~400 行），合理，采纳 |

**复审独有、本意见书漏掉**（已全部核实，见 §五 F10–F20）：N5 溯源失信（**已用 gh 复核成立**）、N1 cwd 矛盾、N2 绝对自导入、N3 pyproject/可安装性、N4 树漏 test_diagnostics、N6 __main__ 可选 vs 验收、P1-1 方法端口矛盾、P1-3 from-import 子模块优先、P2-7 诊断去重键、P2-9 两遍中间产物、P2 其余边角。

**本意见书独有、复审报告没有**（见 §五 F2/F4/S1/S2/S3/S7）：F2 `ast.unparse(node.returns)` 崩溃——**实测证据，唯一**；F4 Attribute 三分支解析；其余为小项。

---

## 一、总体结论

设计方向正确，与 issue #2 schema、issue #3 acceptance criteria、共同语言、2026-08-25 修订高度一致。模块组织维度（薄公共接口 / 扁平 `_` 包 / 不预设协议）完成了一次合格收敛，D14–D16 的论证成立。证据纪律在技术层面无破绽——§2 引用的本地仓库状态、GitHub issue 状态、wayfinder 源文件、`map.md` §Out of scope，逐项复核全部命中。

但动手前必须消化三类问题：

1. **三个阻塞项**（§五 F1/F2/F10）：F1 顶层契约自相矛盾；F2 `ast.unparse(node.returns)` 实测崩溃；F10 修订只在本地未提交、远端 issue #3 与 wayfinder 文件仍是修订前内容——**执行方从 GitHub 接手会实现成 D16 的反面**。
2. **一批执行前钉死项**（F3–F9、F11–F20）：builtins 误报、Attribute 调用、语法错误隔离、venv 排除、标准库归属、dict 契约、cwd 一致性、相对导入、方法端口、from-import 子模块优先等。
3. 以上全部是低成本一次性修复，不动设计骨架。

---

## 二、事实与证据复核

### 核实为真

| 计划主张 | 复核结果 |
|---|---|
| 仅两次提交，HEAD = `f216e26` | ✅ `git log` 一致 |
| 无 parser/ 代码、仓库无任何 `.py` | ✅ 全仓 `find *.py` 为空 |
| GitHub：issue #3 OPEN、#2 CLOSED、#1 OPEN | ✅ `gh issue list --state all` 逐字一致 |
| issue #2 schema：5 顶层键 + AST-only | ✅ `wayfinder/design-data-schema.md` §Resolution:22 |
| grilling 决议（公开/导出、Python、特殊形态不做） | ✅ `wayfinder/grilling-interface-criteria.md` §Resolution:20-23 |
| implement-python-parser §Context 六条 + Amendments 五条 | ✅ 本地文件 §Context:13-18、§Amendments:39-89 原文 |
| 已删除原 note "Keep parser/resolver/reporter behind protocols" | ✅ `git diff` 显示删除属实（**但仅本地**，见 F10） |
| `map.md` §Out of scope（C4/多格式/波动率） | ✅ `wayfinder/map.md:50-54` |
| 核心术语定义 | ✅ `UBIQUITOUS_LANGUAGE.md:9-44` |

### 不实 / 冲突

| 项 | 复核结果 |
|---|---|
| **§2.1 "工作区干净" + §2.4 "本次 ticket 修订" 同时成立** | ❌ **冲突**：修订只存在于本地未提交工作区（`git diff` 证实），远端 issue #3 正文仍含 protocols note、`updated_at == created_at`、远端 wayfinder 文件无 Amendments（gh 实测）。canonical 真源与设计文档描述**分叉**。→ F10 |

### 不可复核

| 项 | 说明 |
|---|---|
| D9/D10/D11/D12/D13 "用户确认（2026-08-25 AskUserQuestion）" | 无独立档案；建议随 PR 落档（F9） |
| 复审报告所述 v1 的包结构 `parser/deep_module_mapper/`、第一轮 15 项清单、Q1–Q6 首轮裁决 | 本意见书未持有这些材料，按复审报告转述；Q1–Q6 的裁决以本意见书 §四为准，若与首轮裁决不一致以本意见书为准并回填 |
| 复审报告 N3 称"stdlib `parser` 模块已在 3.10 移除" | 属实（stdlib 旧 `parser` 模块 3.10 移除），采纳 |

---

## 三、逐条评审

### 决策清单（D1–D16）

| 决策 | 结论 | 评审意见 |
|---|---|---|
| D1 一个 `.py` = 一个模块 | **认可** | |
| D2 端口 = 公开函数/类/`__all__` | **认可（附条件）** | **方法未覆盖**（P1-1 → F16）；`__all__` 提取缺口（S1） |
| D3 六类边 | **认可（附条件）** | `Attribute` 目标未定义（F4）；from-import 子模块优先未定义（F17） |
| D4 AST-only | **认可** | 实测可行 |
| D5 动态导入/未解析 → diagnostics | **认可（附条件）** | builtins/模块内定义排除（F3）；去重键未定义（F19） |
| D6 第三方 → externalModules | **认可（附条件）** | 标准库归属未定案（F7） |
| D7 输出顶层键 | **须先裁决** | 5 键 vs 4 键自相矛盾（F1） |
| D8 第一版 Python | **认可** | |
| D9 模块 id 相对路径 | **认可（附条件）** | 序列化必须 `.as_posix()`（Q1） |
| D10 白名单 + 路径匹配 | **认可（附条件）** | 标准库处理定案（Q3/F7） |
| D11 fixture 形态 | **认可（附条件）** | 补 builtins/语法错误/Attribute/无返回注解 fixture（F3/F4/F5/F2） |
| D12 signature 字符串 | **认可（附条件）** | 补 `params` 列表（Q2）；`returns=None` 崩溃（F2） |
| D13 sites 仅行号 | **认可** | 边按 `(source,target,targetPort,kind)` 合并（S7） |
| D14 单一公共接口 | **认可** | 依据的 canonical 真源分叉，须先推（F10） |
| D15 扁平 `_` 包 | **认可（附条件）** | 包内改用相对导入（F12）；`parser` 顶层名需安装机制锁住（F13） |
| D16 不预设协议 | **认可** | 同上，canonical ticket 需同步（F10） |

### 实现方案（§5.1–5.9）

| 方案 | 结论 | 评审意见 |
|---|---|---|
| 5.1 包结构 | **认可（附条件）** | 树漏 `test_diagnostics.py`（F14）；`__main__.py` 标可选但验收依赖（F15）；缺 pyproject（F13） |
| 5.2 schema 模型 | **否决（按 F1/F8 改）** | Graph 缺 `ports`；dict 字段级契约未钉 |
| 5.3 端口提取 | **否决（按 F2/F16/S1 改）** | `returns=None` 崩溃；方法未提取；`__all__` 只覆盖 Assign+List/Tuple |
| 5.4 边提取 | **否决（按 F3/F4/F17 改）** | builtins/模块内定义误报；Attribute 未定义；from-import 子模块优先未定义 |
| 5.5 扫描器 | **否决（按 F5/F6/F11 改）** | 语法错误未隔离；venv 未排除；`__init__.py` 绝对自导入（F12） |
| 5.6 外部识别 | **否决（按 Q3/F7 改）** | 标准库进不进未定案，与不变量 #3 冲突 |
| 5.7 diagnostics | **认可（附条件）** | kind 扩 `parse_error`（F5）；去重键定义（F19）；message 带动态导入目标（Q5） |
| 5.8 CLI | **认可（附条件）** | cwd 矛盾（F11）；`/tmp`（S4） |
| 5.9 fixture | **认可（附条件）** | 排除断言（F6）、正反用例（F3/F4）、语法错误文件（F5） |

---

## 四、开放点裁决（Q1–Q9）

**Q1**（相对路径 id + `/` 序列化）—— **认可，附 2 条件**：① `root_path.resolve()` 后再 `relative_to`；② 一律 `.as_posix()`（Windows 上 `str(Path)` 是 `\`）。id 与 path 同值冗余可接受。

**Q2**（signature 字符串 vs 结构化参数）—— **裁决：字符串保留，`Port` 补 `params: list[str]`**。AI 描述草稿层要消费参数名，字符串需二次解析（含默认值时 `ast.unparse` 把 `active=True` 整段渲染进字符串，脆弱）；参数名在 AST 免费可得，正是"硬事实"。默认值不必结构化，留后续。

**Q3**（标准库进不进 externalModules）—— **裁决：不进节点、不产生边，文档化忽略**。图谱聚焦目标代码库自身，标准库依赖对架构评审无信号价值；代价（丢失 stdlib 依赖信息）可用 `Module.stdlibImports: [str]` 或独立 ticket 补。**必须同步改不变量 #3**（F7）。

**Q4**（`__all__` 与下划线冲突）—— **裁决：显式 `__all__` 优先**。补充：`__all__` 引用本文件未定义的名称（re-export `from .core import save_user; __all__=["save_user"]`）→ 仍纳入端口（kind="export"），from-import 边照常生成，不重复建端口。

**Q5**（动态导入 severity）—— **裁决：第一版不引入 severity**。但 message 尽量携带目标：`__import__("os")` → 含 `os`；`__import__(user_input)` → 标注"非字面量"。分级留给后继 ticket。

**Q6**（根目录非包时相对导入）—— **裁决：可行**。解析基准是**当前文件所在目录**而非包根：`.core` → 同级 `core.py`，`..core` → 父级 `core.py`，与根目录有无 `__init__.py` 无关。设计须写明算法，并覆盖 `from . import x` / `from .. import y`（`module=None`、`level>0`）（S2）。

**Q7**（`_schema.py` 私有 / TypedDict）—— **裁决：保持私有，但契约载体 = 独立 JSON Schema**。`scan_codebase` 返回 dict 的 **shape 本身就是公共契约**，契约载体不应是某个 Python 文件的可导入性，而应是一份 JSON Schema（或钉死完整示例的 schema 文档）作唯一真源；后端/前端需要类型时从 Schema 生成 TypedDict/TS 类型，而非反向 import parser 内部。这同时倒逼 F1 定案（顶层键 4 or 5，落笔即定）。

**Q8**（dict vs 包装对象）—— **裁决：否决包装类，dict 足够**。`json.dumps(result)` 一行事，包装类纯增公共 API 面积零收益，与 §6.5/§6.6 自己的 YAGNI 原则一致。

**Q9**（`_scanner` 何时拆 `_visitor`）—— **裁决：可接受现状，触发器写死**。落地为可检查条件：「`_scanner.py` 超 ~400 行、或编排与 AST 节点处理无法同屏各读、或测试需要绕过编排单独驱动 visitor 时，拆 `_visitor.py`」。无量化触发器的"到时候再拆"等于永远不拆。

---

## 五、新发现问题（含两份评审，来源标注）

### 阻塞级

| # | 来源 | 问题 | 要求 |
|---|---|---|---|
| F1 | 本+复审 P0-1 | **顶层输出契约自相矛盾**：§2.3（L86）引 issue #2 确认 5 顶层键（含 `ports`）；§5.2 `Graph`（L189）与 §7 不变量 #6（L414）只实现 4 键、丢 `ports`。不裁决则 "Output matches the schema confirmed in issue #2" 不成立。 | 按 issue #2 字面 **5 键落地**：Graph 增顶层 `ports` 扁平列表（每条带 `moduleId`），模块内嵌保留；统一 §2.3/§5.2/§7#6/§8.1 四处。 |
| F2 | 本（实测） | **§5.3 signature 在无返回注解时崩溃**：实测 `ast.unparse(node.returns)` 当 `returns is None` 抛 `AttributeError`。绝大多数 Python 函数无返回注解。 | `(" -> " + ast.unparse(node.returns)) if node.returns is not None else ""`；docstring 取第一句判 None；fixture 加无返回注解函数。 |
| F10 | 复审 N5（已复核） | **溯源失信，canonical 分叉**：§2.4 "本次 ticket 修订" 只在本地未提交；远端 issue #3 正文仍含 protocols note、`updated_at==created_at`、远端 wayfinder 文件无 Amendments（gh 实测）。D14–D16 的依据在 canonical 真源**不可复现**；从 GitHub 接手的执行者会实现成 D16 反面。 | ① 提交并推送本地 Amendments；② issue #3 编辑正文或追加评论登记修订；③ 同步后更新 §2.1/§2.2 真值时点。 |

### 重要级

| # | 来源 | 问题 | 要求 |
|---|---|---|---|
| F3 | 本+复审 P0-4 | **unresolved_symbol 吞 builtins 与模块内定义**：§5.4 只排除"局部变量/参数"。`print()`/`len()`、同模块内定义函数全落诊断，dpiagnostics 被淹没，不变量 #5 失效。 | 解析顺序钉死：模块级 imports → 模块级 defs（跳过）→ builtins（`dir(builtins)`，跳过）→ 其余才记诊断。fixture 断言 builtins 调用**不产生**诊断。 |
| F4 | 本 | **`Attribute` 调用目标（`obj.method()`）未定义**：call/inheritance/annotation/decorator 解析表只写"被调用名"。`user.save()`、`@app.route("/")`、`obj.field: T` 是真实代码最常见形态。 | 补规则：解析 func 的 base——base 是导入模块 → 边（targetPort=attr）；base 是局部/参数/模块内定义 → 跳过；base 未知模块级名 → 诊断。 |
| F5 | 本+复审 P0-2 | **`ast.parse` 语法错误未隔离**：真实仓库必有无法解析文件，抛 `SyntaxError` 崩掉整个扫描。 | 每文件 try/except `SyntaxError` → `parse_error` 诊断（含文件名/行号），继续；诊断 kind 扩 3 类；用 `tokenize.open()` 读源码解决编码。 |
| F6 | 本+复审 P0-3 | **`rglob("*.py")` 扫入 venv/噪音目录**：对 `agent-lib/` 这类带 venv 的真实仓库产生几千个假模块。 | 内置排除集：`.git/__pycache__/.venv/venv/node_modules/dist/build`（可配置）；不变量 #1 加"未被排除"限定；fixture 加排除断言。 |
| F7 | 本+复审 P1-2 | **标准库处理未定案，且与不变量 #3 冲突**：§5.6（L263）"可选记录或忽略，由实现定" vs §7 不变量 #3（L412）"所有 import 都产生边或 externalModules"。 | 按 Q3 裁决：本地→边、第三方→节点、标准库→忽略；不变量 #3 改为"所有**本地** import 产生边、第三方产生 externalModules、标准库忽略（文档化）"。 |
| F8 | 本+复审 Q7 | **返回 dict 字段级契约未钉死**：schema 文档只列顶层键；字段名/kind 枚举/大小写（`moduleId` vs `module_id`）未定义。 | 随 PR 提交一份 JSON Schema（或钉死完整示例）作唯一真源，含 1 本地模块 + 1 第三方 + 1 诊断的完整 JSON。 |
| F11 | 复审 N1 | **`python -m parser` cwd 自相矛盾**：§8.3（仓库根 cwd）与 §8.4（`cd ...\parser` 后 `python -m parser`）必有一个跑不通——包内 cwd 找不到名为 `parser` 的包。 | 统一仓库根执行：`cd "deep-module-mapper"`；`python -m pytest parser/tests`；`python -m parser parser/tests/fixtures/sample_pkg --output graph.json`。 |
| F12 | 复审 N2 | **包内绝对自导入脆弱**：`from parser._scanner import scan_codebase` 仅当仓库根在 `sys.path` 时成立；否则同一模块以两身份导入，符号表分裂。 | 改 `from ._scanner import scan_codebase`，规定"包内一律相对导入"。 |
| F13 | 复审 N3 | **pyproject 消失，包不可安装，CLI 全靠 cwd**：无 `pip install -e .` 则 `import parser` 只在仓库根有效；`requires-python` 无处安放；顶层名 `parser` 过泛（遮蔽风险）。 | 恢复最小 pyproject（`name`、`requires-python = ">=3.10"`、pytest 配置），与 F11 的"仓库根执行"二选一或并存，文档写死一种。 |
| F14 | 复审 N4 | **§5.1 目录树漏列 `test_diagnostics.py`**（树 4 个 vs §8.1 5 个）。 | 补入目录树。 |
| F15 | 复审 N6 | **`__main__.py` 标注"可选"但验收命令依赖它**。 | 二选一写死：`__main__.py` 改必选，或验收命令改 `python scripts/run_parser.py ...`。 |
| F16 | 复审 P1-1 | **方法是否端口矛盾**：§2.3 引 grilling 决议"公开函数 / 导出符号（**函数、方法**、导出类）"含"方法"，但 D2/§5.3 只提取模块级函数/类、不提取类内方法，`Port.kind` 无 `"method"`。 | 裁决：类内公开方法是否作为端口（建议：第一版不单列方法，在 D2 中登记对引文的收紧；或按类端口下枚举公开方法），并统一引文表述。 |
| F17 | 复审 P1-3 | **from-import 子模块优先未定义**：`from pkg import core` 应按 Python 语义优先解析为子模块 `pkg/core.py`，而非 `pkg/__init__.py` 的端口 `core`；设计"target 按模块名解析"会错连 `__init__.py`。 | from-import 解析顺序：子模块（`module`+`.`+`alias` 映射到文件）→ 再尝试 `__init__.py` 端口 → 再 external。fixture 加 `from pkg import core` 用例。 |
| F18 | 本 S3 + 复审 P1-5 | **字符串注解 / Subscript 漏边**：`from __future__ import annotations` 下 `ast.unparse` 输出带引号（实测 `"'User'"`）；`Optional[User]` 的 Subscript 未剥壳，`User` 找不到。 | 注解解析剥 `Subscript`/`Constant`（字符串），归一后查符号表；signature 对字符串注解 strip 引号。 |
| F19 | 复审 P2-7 | **诊断去重键未定义**：同名符号 50 处出现是 50 条还是 1 条无答案。 | 定义去重键：`(kind, moduleId, line)` 或 `(kind, moduleId, name)`（按意图选），写进 §5.7。 |
| F20 | 复审 P2-9 | **两遍遍历中间产物未定义**：pass1 产出、pass2 消费的中间结构（`RawReference` 之类）没定义，两个函数衔接处易脱节。 | 定义中间结构（如 `RawReference`：node/name/kind/line/scope），写明 pass1→pass2 契约。 |

### 建议级

| # | 来源 | 问题 | 要求 |
|---|---|---|---|
| S1 | 本+复审 P2 | **`__all__` 只覆盖 `ast.Assign`+`List/Tuple`**：漏 `AnnAssign`（`__all__: list[str] = [...]`）、动态构造、`__all__ += [...]`、re-export 重影。 | 第一版可接受，记入"已知缺口"节。 |
| S2 | 本 | **`from . import x` / `from .. import y`（`module=None`）** 在 §5.4 表未覆盖。 | 实现时处理 `level>0 且 module=None`。 |
| S4 | 本+复审 P2-4 | **CLI 测试 `--output /tmp/graph.json`** 在 Windows 不成立。 | 改仓库内临时路径（并入 F11 命令）。 |
| S6 | 本+复审 P1-4 | **`requires-python` 未声明**：`sys.stdlib_module_names`（3.10+）与 `ast.unparse`（3.9+）有版本前提。 | 声明 `>=3.10`（并入 F13 的 pyproject）。 |
| S7 | 本 | **边去重/排序未定义**：多 sites 应合并为一条边。 | 按 `(source,target,targetPort,kind)` 合并、聚合 sites、稳定排序。 |
| S8 | 复审 P2 其余 | 星号导入、函数内/条件导入、装饰器解包、外部模块名归一 | 可与实现并行；已知缺口节记录。 |
| F9 | 本 | **grilling AskUserQuestion 结论未落档**（D9/D10/D11/D12/D13 依据）。 | 随 PR 提交 `wayfinder/grilling-decisions/issue-3-parser-design.md`。 |

---

## 六、通过条件清单（执行前勾选）

**阻塞级（缺一不进实现）**
- [ ] **F1**：裁决 `ports` 顶层键（建议 5 键），统一 §2.3 / §5.2 / §7#6 / §8.1
- [ ] **F2**：signature 防御 `returns is None`；fixture 加无返回注解函数
- [ ] **F10**：推送本地 Amendments、同步 issue #3（登记删除 protocols note）、更新真值时点

**重要级**
- [ ] **F3**：解析顺序钉死 builtins / 模块内定义排除；改不变量 #5；fixture 正反用例
- [ ] **F4**：补 `Attribute` 目标三分支解析规则
- [ ] **F5**：`tokenize.open()` + `parse_error` 诊断 + 单文件故障隔离 + 新不变量
- [ ] **F6**：排除清单 + 配置 + fixture 排除断言；不变量 #1 加限定
- [ ] **F7**：按 Q3 裁决定标准库处理；同步改不变量 #3
- [ ] **F8**：随 PR 提交 JSON Schema（或钉死示例）契约
- [ ] **F11**：统一为仓库根执行命令
- [ ] **F12**：`from ._scanner import scan_codebase`，规定包内相对导入
- [ ] **F13**：恢复最小 pyproject（`>=3.10` + pytest 配置）
- [ ] **F14**：目录树补 `test_diagnostics.py`
- [ ] **F15**：`__main__.py` 必选 或 验收命令改 scripts
- [ ] **F16**：裁决方法是否端口，统一引文表述
- [ ] **F17**：from-import 子模块优先解析；fixture 加用例
- [ ] **F18**：注解剥 Subscript/字符串；signature strip 引号
- [ ] **F19**：诊断去重键定义
- [ ] **F20**：两遍遍历中间结构定义

**裁决落地与建议**
- [ ] Q1–Q9 裁决并入 §5 正文，§9 标记"已裁"，§10 回填两轮评审记录
- [ ] Q2：`Port.params`；Q4：re-export 语义；Q6/S2：相对导入算法 + `from . import x`
- [ ] S1/S4/S6/S7/S8：已知缺口节记录；F9：grilling 结论落档

## 七、结语

两份评审独立命中同一批核心缺陷（8 处重叠），说明设计骨架与证据基础经得起两双眼睛；互补部分恰好覆盖了彼此盲区——复审补上了**溯源闭环**（F10）与**可执行性细节**（F11–F15），本意见书补上了**实测崩溃证据**（F2）与 **AST 节点形态**（F4/F18）。修完 3 个阻塞项后，其余均为低成本一次性补丁。建议以 §六清单作为实现 PR 的自检表，两份评审意见书连同 grilling 决策一并随 PR 落档。

—— 评审方（合并版：独立复核 @ `f216e26` + gh CLI + Python 3.13.11 实测；复审报告主张已逐项复核，2026-08-26）
