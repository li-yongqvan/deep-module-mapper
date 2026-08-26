# #3 Implement Python AST parser — 设计文档（供评审）

> 文档用途：交付专业评审 agent 的评审对象。范围 = 背景 / 真值核对 / 决策记录 / 实现方案 / 不变量 / 验证。
> 溯源约定：**事实**标来源（代码 `file:line` / 命令输出 / GitHub issue / grilling 用户确认）；**判断性裁决**单独标注【决策】并给出理由与备选，不冒充事实。
> 数据时点：2026-08-26（真值核对执行日；本次为 v3，消化评审意见书《implement-python-parser-设计文档-评审意见书.md》）。
> 评审状态：**有条件通过**（评审意见书 v2，合并两份评审）。阻塞项 F1/F2/F10 已在本版消化。

## 0. 项目上下文（给零背景评审 agent 先读本节）

**这是什么**：Deep Module Mapper（深度模块地图工具），一个本地 Web 应用，指向任意代码库后自动提取其**模块**与**接口依赖**，以规则几何体可视化每个模块的接口功能与职责；并提供「自定义依赖画布」供用户拖拽设计理想架构，由云端模型输出结构化评审。

- 项目目录：`C:/Users/liyongquan/agent panel/deep-module-mapper/`。
- GitHub 仓库：https://github.com/li-yongqvan/deep-module-mapper
- Canonical wayfinder map：GitHub issue #1 — https://github.com/li-yongqvan/deep-module-mapper/issues/1
- 共同语言源文件：`deep-module-mapper/UBIQUITOUS_LANGUAGE.md`

**核心术语**（评审本设计必须理解）：
- **模块**：一个自包含的实现单元，由**实现**和**端口**组成。第一版边界：一个 `.py` 文件 = 一个模块。
- **端口**：模块对外暴露的连接面，即公开函数、类、`__all__` 导出符号。
- **接口**：端口的使用说明书。第一版由解析器提取硬事实（函数名、参数、返回值、docstring 第一句），后续由本地模型润色描述。
- **依赖**：一个模块的端口使用了另一个模块的端口所构成的关系。
- **依赖边**：可视化图上的箭头，带 kind（import / from-import / call / inheritance / annotation / decorator）和发生位置 sites。
- **解析器**：后端中读取代码库、提取模块/端口/依赖的组件。本票即实现第一版 Python 解析器。

**前序工作与本票位置**：
- issue #2「Design: data schema and API contract」已关闭，确认了 JSON 输出顶层为 `modules / ports / edges / externalModules / diagnostics`（`wayfinder/design-data-schema.md` §Resolution）。
- issue #3 是当前 open frontier ticket，目标是把 schema 落地为可运行的 Python AST 解析器。

## 1. 背景与目标

- **需求来源**：GitHub issue #3「Implement Python AST parser」— https://github.com/li-yongqvan/deep-module-mapper/issues/3
- **本地镜像**：`wayfinder/implement-python-parser.md`
- **目标**：实现第一版 Python AST 解析器，暴露单一公共接口 `scan_codebase(root_path: Path) -> dict`，接受仓库根路径，扫描所有 `.py` 文件，输出符合 issue #2 schema 的模块、端口、依赖边、第三方外部模块和诊断信息，并附带 CLI/测试脚本。
- **评审输入**：`wayfinder/implement-python-parser-评审意见书.md`（2026-08-26，合并两份评审）。本版已消化其全部阻塞/重要/建议级意见，实现以 §5-§8 为准。

## 2. 真值核对（数据来源，全部可复现）

> 本节所有命令在 `C:/Users/liyongquan/agent panel/deep-module-mapper/` 下执行，数据时点 2026-08-26。

### 2.1 代码真值（本地仓库实查）

```bash
cd "C:\Users\liyongquan\agent panel\deep-module-mapper" && git status --short && git log --oneline -3
```

输出摘录（2026-08-26）：
```
 f216e26 Close schema ticket, add parser implementation ticket, sync map
19ae2ac Initial commit: wayfinder map, research reports, prototype, and ubiquitous language
```
（`git status` 在本版修订时已包含待提交的 Amendments，见 §2.4。）

→ **事实：实现起步时仓库仅两次提交；`parser/` 代码由本票新建。**

### 2.2 GitHub 状态（本地 gh CLI 实查，2026-08-26）

```bash
gh issue list --limit 10 --state all
```

输出摘录：
```
3	OPEN	Implement Python AST parser	wayfinder:task	2026-08-25T15:02:19Z
2	CLOSED	Design: data schema and API contract	wayfinder:grilling	2026-08-25T15:01:02Z
1	OPEN	Deep Module Mapper — Wayfinder Map	wayfinder:map	2026-08-25T15:03:56Z
```

→ **事实：issue #3 为 OPEN，issue #2 为 CLOSED。**

⚠️ **修正（F10）**：本版修订时，远端 issue #3 正文仍含原 protocols note、`updated_at == created_at`，远端 wayfinder 文件无 Amendments——canonical 真源与本地分叉。**F10 的执行（提交推送本地 Amendments + 更新 issue #3 正文）已纳入本票 §8.5。**

### 2.3 已确认 schema 与接口范围

来自 `wayfinder/design-data-schema.md` §Resolution：
- Core data model: JSON with `modules`, `ports`, `edges`, `externalModules`, `diagnostics`（**5 个顶层键**）。

来自 `wayfinder/grilling-interface-criteria.md` §Resolution：
- 第一版接口识别范围：**公开函数 / 导出符号**（函数、方法、导出类）。
- 描述生成策略：规则提取硬事实 + 本地模型润色一句话描述。
- 第一版支持语言：**Python**。

来自 `wayfinder/implement-python-parser.md` §Context：
- Module boundary: one `.py` file = one module.
- Port: public functions, classes, and `__all__` exports.
- Edge kinds: import / from-import / call / inheritance / annotation / decorator.
- Dynamic imports and unresolved symbols become diagnostics.
- Third-party packages become external module nodes.

→ **事实：上述范围已在前序 tickets 中确认，构成本票输入约束。**

### 2.4 本票修订与评审记录（2026-08-25/26）

- `implement-python-parser.md` 于 2026-08-25 增加 `## Amendments from 2026-08-25 review`，核心 5 条：①单一公共接口 `scan_codebase`；②`_` 前缀私有内部文件；③拆分条件；④第一版单语言；⑤Jedi 保持可选。
- 本票于 2026-08-26 完成独立评审（合并两份），结论**有条件通过**，阻塞项 3 个（F1/F2/F10）。评审意见书：`wayfinder/implement-python-parser-评审意见书.md`。
- 本版设计文档消化全部评审意见，见 §3-§8 各处回指。

## 3. Grilling 决策记录

| 编号 | 决策问题 | 定案 | 依据 |
|---|---|---|---|
| D1 | 模块边界 | **一个 `.py` 文件 = 一个模块** | `wayfinder/design-data-schema.md` §Context；用户确认（2026-08-25）；评审认可 |
| D2 | 端口识别范围 | **模块级公开函数、类、`__all__` 导出符号**；**类内公开方法不单列为端口**（作为类端口的组成部分，见 §6.8） | `wayfinder/grilling-interface-criteria.md` §Resolution；评审 F16 裁决；用户确认（2026-08-25） |
| D3 | 依赖边类型 | **import / from-import / call / inheritance / annotation / decorator** | `wayfinder/implement-python-parser.md` §Context；用户确认（2026-08-25）；评审认可（附 F4/F17/F18 修正，见 §5.4） |
| D4 | 解析策略 | **AST-only（stdlib `ast`），Jedi 后续可选** | 用户确认（2026-08-25）；评审实测认可 |
| D5 | 动态导入/未解析符号 | **进入 `diagnostics`**，解析顺序钉死：imports → 模块内 defs → builtins → 其余才记诊断 | 用户确认（2026-08-25）；评审 F3 修正 |
| D6 | 第三方包 | **归入 `externalModules` 节点** | 用户确认（2026-08-25）；评审认可 |
| D7 | 输出格式 | **JSON，顶层键 `modules / ports / edges / externalModules / diagnostics`（5 键）** | `wayfinder/design-data-schema.md` §Resolution；评审 F1 裁决（本版统一 5 键，顶层 `ports` 为扁平列表，每条带 `moduleId`） |
| D8 | 第一版语言 | **Python** | `wayfinder/grilling-interface-criteria.md` §Resolution；用户确认（2026-08-25） |
| D9 | 模块 id 格式 | **相对路径**，`root_path.resolve()` 后 `relative_to`，序列化一律 `.as_posix()` | 用户确认（2026-08-25）；评审 Q1 条件 |
| D10 | 标准库/第三方/本地包识别 | **标准库白名单 + 内部路径匹配** | 用户确认（2026-08-25）；评审认可 |
| D11 | 测试 fixture 形态 | **在 `parser/tests/fixtures/` 下搭微型 Python 项目** | 用户确认（2026-08-25）；评审补充 F3/F4/F5/F6 用例 |
| D12 | 端口 signature 内容 | **参数名 + 返回值标记 + varargs 标记的格式化字符串**，另补 `params: list[str]` 结构化参数名列表 | 用户确认（2026-08-25）；评审 Q2 裁决 |
| D13 | edges sites 粒度 | **仅记录行号**；边按 `(source, target, targetPort, kind)` 合并、聚合 sites、稳定排序 | 用户确认（2026-08-25）；评审 S7 |
| D14 | 公共接口形态 | **单一函数 `scan_codebase(root_path: Path) -> dict`** | `implement-python-parser.md` §Amendments 1；用户确认（2026-08-25） |
| D15 | 内部模块组织 | **扁平 `parser/` 包，内部文件以 `_` 前缀表示私有**；包内一律相对导入 | `implement-python-parser.md` §Amendments 2；评审 F12；用户确认（2026-08-25） |
| D16 | 多语言扩展协议 | **第一版不做抽象协议，不预留多语言接口** | `implement-python-parser.md` §Amendments 4；用户确认（2026-08-25） |
| D17 | 标准库处理 | **不进节点、不产生边、文档化忽略**（可选：未来补 `Module.stdlibImports`） | 评审 Q3/F7 裁决 |
| D18 | `__all__` 与下划线冲突 | **显式 `__all__` 优先**；`__all__` 引用本文件未定义名称（re-export）→ 仍纳入端口（kind="export"），from-import 边照常生成，不重复建端口 | 评审 Q4 裁决 |
| D19 | 动态导入诊断 | **第一版不引入 severity**，但 message 尽量携带目标（`__import__("os")` → 含 `os`；非字面量 → 标"非字面量"） | 评审 Q5 裁决 |
| D20 | 语法错误处理 | **单文件故障隔离**：`tokenize.open()` 读源码，`ast.parse` 抛 `SyntaxError` → `parse_error` 诊断（含文件名/行号），继续扫描 | 评审 F5 裁决 |
| D21 | 目录排除 | **内置排除集**：`.git` / `__pycache__` / `.venv` / `venv` / `node_modules` / `dist` / `build`（可配置） | 评审 F6 裁决 |
| D22 | 输出契约载体 | **独立 JSON Schema（或钉死完整示例）作唯一真源**，随 PR 提交 | 评审 Q7/F8 裁决 |
| D23 | 打包形态 | **最小 pyproject**：`name`、`requires-python = ">=3.10"`、pytest 配置；CLI 走 `python -m parser`（必选 `__main__.py`） | 评审 F13/F15/S6 裁决 |

## 4. 范围收敛与明确不做

| 项 | 决策 | 依据 |
|---|---|---|
| 不使用 Jedi 做解析 | 不做（本期） | D4；Jedi 放后续关卡 |
| 不解析 JS/TS 等其他语言 | 不做（本期） | D8；D16 |
| 不识别 HTTP 端点、CLI 子命令、事件监听等特殊端口 | 不做（本期） | `wayfinder/grilling-interface-criteria.md` §Resolution |
| 不做 AI 描述润色 | 不做（本期） | parser 只输出硬事实 |
| 不做增量/差异扫描 | 不做（本期） | 第一版全量扫描 |
| 不做 WebSocket/轮询实时刷新 | 不做（本期） | 解析器只负责一次性扫描输出 JSON |
| 不做 C4 视图、多格式导出、Git 历史波动率 | 不做（本期） | `wayfinder/map.md` §Out of scope |
| 不单列类内公开方法为端口 | 不做（本期） | D2；深模块原则：方法归入类端口内部，接口面收窄 |
| 标准库不产生节点/边 | 不做（本期） | D17 |
| 动态导入 severity 分级 | 不做（本期） | D19；留后续 ticket |
| `__all__` 覆盖 AnnAssign / 动态构造 / `__all__ += [...]` | 不做（本期，记已知缺口） | 评审 S1；第一版仅覆盖 `Assign` + `List/Tuple` |
| 星号导入 / 函数内条件导入 / 装饰器解包 / 外部模块名归一 | 不做（本期，记已知缺口） | 评审 S8 |
| 包装类（`Graph` 对象封装） | 不做（本期） | 评审 Q8：否决，dict 足够 |

## 5. 实现方案

### 5.1 创建解析器包结构（含 pyproject）

在仓库根目录新建扁平 `parser/` 包：

```
deep-module-mapper/
└── parser/
    ├── pyproject.toml          # name、requires-python = ">=3.10"、pytest 配置
    ├── __init__.py             # 公共 API：from ._scanner import scan_codebase
    ├── __main__.py             # CLI 入口：python -m parser <repo> [--output]
    ├── _schema.py              # 内部 dataclass 模型（私有）
    ├── _scanner.py             # 模块发现 + 两遍遍历编排
    ├── _ports.py               # 端口提取
    ├── _edges.py               # 依赖边解析（imports + references）
    ├── _external.py            # 第三方/标准库识别
    ├── _diagnostics.py         # 诊断收集（含 parse_error）
    └── tests/
        ├── conftest.py
        ├── fixtures/
        │   ├── sample_pkg/
        │   │   ├── __init__.py     # __all__ 定义 + re-export
        │   │   ├── core.py         # 公开函数/类/带注解/带 docstring/无返回注解
        │   │   ├── utils.py        # 公开 helper + builtins 调用 + obj.method()
        │   │   └── main.py         # import 六类边 + 第三方 + 动态导入
        │   ├── broken_syntax.py    # 语法错误文件（F5）
        │   └── venv_stub/          # 模拟被排除目录（F6）
        ├── test_scan_codebase.py   # 端到端
        ├── test_ports.py
        ├── test_edges.py
        ├── test_external.py
        └── test_diagnostics.py
```

依据：评审 F13/F14/F15（pyproject、`test_diagnostics.py`、`__main__.py` 必选）；`implement-python-parser.md` §Amendments 2。

### 5.2 定义 schema 模型（_schema.py + JSON Schema 契约）

`_schema.py` 定义内部 dataclass，**顶层输出契约 = 独立 JSON Schema 文件**（`parser/schema.json` 或文档钉死完整示例，随 PR 提交），两者保证一致。

**输出 JSON 结构（5 顶层键）**：

```json
{
  "modules": [
    {
      "id": "sample_pkg/core.py",
      "path": "sample_pkg/core.py",
      "ports": [
        {"kind": "function", "name": "save_user", "line": 3,
         "signature": "save_user(name, email, *, active=True) -> User",
         "params": ["name", "email", "active"], "docstring": "Persist a user."}
      ]
    }
  ],
  "ports": [
    {"moduleId": "sample_pkg/core.py", "kind": "function", "name": "save_user",
     "line": 3, "signature": "...", "params": ["name", "email", "active"],
     "docstring": "Persist a user."}
  ],
  "edges": [
    {"source": "sample_pkg/main.py", "target": "sample_pkg/core.py",
     "targetPort": "save_user", "kind": "call", "sites": [{"line": 5}]}
  ],
  "externalModules": [
    {"id": "requests", "name": "requests", "kind": "third_party"}
  ],
  "diagnostics": [
    {"kind": "dynamic_import", "moduleId": "sample_pkg/main.py",
     "line": 9, "message": "dynamic import of 'os'"}
  ]
}
```

- `Port`（内嵌 + 顶层扁平两种形态）: kind（"function" | "class" | "export"）, name, line, signature, params（list[str]）, docstring（可选）。
- `Module`: id（相对路径 `.as_posix()`）, path, ports。
- `Edge`: source（模块 id）, target（模块 id）, targetPort（可选）, kind, sites（`[{"line": n}]`）。
- `ExternalModule`: id, name, kind（"third_party"）。
- `Diagnostic`: kind（"dynamic_import" | "unresolved_symbol" | "parse_error"）, moduleId, line, message。

**去重键**（F19）：诊断按 `(kind, moduleId, line)` 去重；边按 `(source, target, targetPort, kind)` 合并、聚合 sites、稳定排序（按 source 再 line）。

依据：D7（F1 统一 5 键）、D12（Q2 补 params）、D22（F8 JSON Schema）、F19、S7。

### 5.3 端口提取（_ports.py）

对每个 `.py` 文件的 AST 返回端口列表：

1. **公开函数**：模块级 `ast.FunctionDef` / `ast.AsyncFunctionDef`，`name` 不以 `_` 开头。
   - signature 组装：`ast.unparse(node.args)` 的紧凑形式；**返回值防御（F2）**：`(" -> " + ast.unparse(node.returns)) if node.returns is not None else ""`。
   - `params`：从 `node.args` 提取参数名列表（posonlyargs + args + kwonlyargs + vararg + kwarg，按序，去默认值/注解只留名字）。
   - line = `node.lineno`；docstring = `ast.get_docstring(node)` 第一句（判 None）。
2. **公开类**：模块级 `ast.ClassDef`，`name` 不以 `_` 开头。
   - signature = `ClassName(Base1, Base2)`（bases 用 `ast.unparse`，剥 Subscript/字符串）。
   - line / docstring 同上。
3. **`__all__` 导出符号**（D18/Q4）：模块级 `ast.Assign` 目标为 `__all__` 且值是 `List/Tuple`，取字符串字面量元素 → kind="export"；若名称未在本文件定义（re-export），仍纳入端口，from-import 边照常生成且不重复建端口。

类内公开方法**不**单列端口（D2/F16，见 §6.8）。

依据：D2、D12、F2、F16、Q2、Q4、S1（已知缺口）。

### 5.4 依赖边提取（_edges.py + _scanner.py）

`_scanner.py` 做两遍遍历，中间结构（F20）：

- **pass1**：逐文件 `ast.parse` → 产出 `ModuleRecord`（id/path/ports）+ `RawImport`（kind/name/alias/level/line）+ `RawReference`（node/name/kind/line/scope/base）列表。
- **pass2**：构建全局模块索引（id → 端口表 + 包映射），消费 RawImport/RawReference 解析为 `Edge`，产出 externalModules 候选 + unresolved_symbol 诊断。

**pass1 → pass2 契约**（F20）：
```python
@dataclass
class RawImport:
    kind: str            # "import" | "from_import"
    module: str | None   # ImportFrom 的 module（可能 None）
    level: int           # 相对导入层级，0 = 绝对
    name: str            # 导入的符号/模块名
    alias: str | None    # as 别名
    line: int

@dataclass
class RawReference:
    name: str            # 完整被引用名（如 "user.save"）
    kind: str            # "call" | "inheritance" | "annotation" | "decorator"
    base: str | None     # Attribute 的 base（如 "user"），None 表示 Name
    line: int
    scope: str           # "module" | "function" | "class"
```

**六类边 + Attribute 三分支（F4/F17/F18）**：

| kind | AST 节点 | 解析规则 |
|---|---|---|
| import | `ast.Import` | 每个 alias → 本地模块 / 第三方 / 标准库（D17） |
| from-import | `ast.ImportFrom` | **子模块优先（F17）**：`module`+`.`+`alias` 映射到文件 → 再尝试 `__init__.py` 端口 → 再 external；`level>0 且 module=None`（`from . import x`）按相对路径解析（S2） |
| call | `ast.Call` | 解析 `func`：base 是 Name → 查符号表；base 是 Attribute → 见下；base 是其他（如 `self.x()`、lambda）→ 跳过 |
| inheritance | `ast.ClassDef.bases` | 同 call 规则 |
| annotation | `ast.AnnAssign.annotation` / 函数参数注解 / 返回值注解 | **剥 Subscript/Constant 字符串（F18）**后查符号表；signature 对字符串注解 strip 引号 |
| decorator | `ast.FunctionDef.decorator_list` / `ClassDef.decorator_list` | 同 call 规则 |

**Attribute 三分支（F4）**：
1. base 是导入的模块名（如 `import utils; utils.save_user()`）→ 生成边，targetPort=attr。
2. base 是局部变量 / 参数 / 模块内已定义符号（`self.save()`、`obj.field()`）→ 跳过，不生成边不产生诊断。
3. base 是未知模块级名 → unresolved_symbol 诊断。

**解析顺序（F3，优先级从高到低）**：
1. 模块级 imports（当前文件符号表）。
2. 模块级 defs / 类（跳过——模块内引用不构成跨模块边）。
3. builtins（`dir(builtins)`，跳过）。
4. 其余才记 unresolved_symbol 诊断。

依据：D3、D5、F3、F4、F17、F18、F20、S2、S8（已知缺口）。

### 5.5 仓库扫描器（_scanner.py）

`scan_codebase(root_path: Path) -> dict`（§5.4 的两遍遍历 + 步骤）：

1. `root_path.resolve()`；`rglob("*.py")` 收集，**过滤 D21 排除集**。
2. pass1：逐文件 `tokenize.open()` 读源码（F5 编码安全）→ `ast.parse`；`SyntaxError` → `parse_error` 诊断，**跳过该文件继续**（F5）。
3. 调用 `_ports.extract_ports` 提取端口（含顶层扁平 `ports` 列表生成）。
4. 调用 `_edges.extract_imports` 收集 import / from-import 边 + external 候选。
5. 构建全局模块索引；调用 `_edges.extract_references` 收集 call / inheritance / annotation / decorator 边。
6. 调用 `_external.classify` 分类；调用 `_diagnostics.collect` 汇总（含去重）。
7. 返回 5 顶层键的 dict。

`__init__.py`：`from ._scanner import scan_codebase`（相对导入，F12）。

依据：D14、D21、F5、F6、F11、F12。

### 5.6 外部模块识别（_external.py）

- 白名单 `sys.stdlib_module_names`（Python 3.10+，S6）。
- 判断顺序：
  1. 映射到仓库内 `.py` 文件（含包 `__init__.py`）→ 本地模块。
  2. 白名单 → **标准库，忽略**（D17，不进节点不产生边）。
  3. 其余 → `externalModules`（kind="third_party"）。
- 相对导入（level>0）基于当前文件所在目录解析（Q6/S2），与根目录有无 `__init__.py` 无关。

依据：D10、D17、Q6、S6。

### 5.7 diagnostics（_diagnostics.py）

三类诊断（F5 扩类）+ 去重（F19）：

1. **dynamic_import**：`__import__`、`importlib.import_module`；message 携带目标（字面量 → 名字；否则标"非字面量"）（Q5）。
2. **unresolved_symbol**：按 F3 解析顺序，仅"其余"才记。
3. **parse_error**：`ast.parse` 抛 `SyntaxError`（含文件名/行号），不中断扫描。

去重键 `(kind, moduleId, line)`；按 (moduleId, line) 稳定排序。

依据：D5、D19、D20、F5、F19。

### 5.8 CLI（__main__.py）

`__main__.py` **必选**（F15），薄 wrapper 仅调用公共 API：

```bash
python -m parser <repo_path> [--output graph.json]
```

- 统一**仓库根 cwd 执行**（F11/S4）：`cd deep-module-mapper` 后运行；`--output` 默认写 stdout，指定文件用仓库内路径。
- 内部仅 `from . import scan_codebase`，不引用 `_` 前缀模块。

依据：D14、F11、F15、S4。

### 5.9 测试 fixture

`parser/tests/fixtures/` 下：
- `sample_pkg/`：`core.py`（公开函数/类/注解/docstring/**无返回注解**）、`utils.py`（helper + **builtins 调用** + **`obj.method()`** + **`from pkg import core`**）、`main.py`（六类边 + 第三方 `requests` + 动态导入 + **Attribute 调用**）、`__init__.py`（`__all__` + **re-export**）。
- `broken_syntax.py`：**语法错误文件**（F5 正用例）。
- `venv_stub/`：**排除目录**（F6 正用例）。

测试断言（每项对应用例）：
- 端口：`core.py` 含 `save_user`、`User`；**无返回注解函数不崩溃**（F2）；builtins 调用**不产生**诊断（F3）；`obj.method()` 不误报（F4）。
- 边：`main → core` call 边；`from sample_pkg import core` 解析为**子模块文件**而非 `__init__.py` 端口（F17）；`import utils; utils.x()` 生成 targetPort 边（F4）。
- externalModules：含 `requests`（F6 的 venv 不进来）；标准库（如 `json`）**不出现**（D17）。
- diagnostics：dynamic_import ≥1、unresolved_symbol ≥1、**parse_error 含 broken_syntax.py**（F5）。
- 排除：`venv_stub/` 下 `.py` **不计入 modules**（F6）。

依据：D11、F2、F3、F4、F5、F6、F17、Q4。

## 6. 关键设计裁决（【决策】，含理由与备选）

### 6.1 模块 id 用相对路径而非点分 Python 模块名
- **定案【决策】**：`root_path.resolve()` 后 `relative_to` 得到相对路径，序列化一律 `.as_posix()`（Windows 上 `str(Path)` 是 `\`）。
- **理由**：与文件系统一一对应；不依赖 PYTHONPATH；跨平台统一 `/`。
- **备选**：点分模块名（需知包根、相对导入复杂）；文件名（跨目录冲突）。评审 Q1 附条件已采纳。

### 6.2 用标准库白名单 + 内部路径匹配识别包类型
- **定案【决策】**：先映射仓库内文件 → 白名单判标准库（D17 忽略）→ 其余第三方 externalModules。
- **理由**：零依赖、不执行代码、`sys.stdlib_module_names` 官方维护。
- **备选**：实际 import 检测 site-packages（执行代码副作用）；全当 external（污染图谱）。

### 6.3 AST-only 而非 import-time 分析
- **定案【决策】**：纯 AST 静态分析。
- **理由**：不执行代码、零依赖、能捕获源码层六类关系。
- **备选**：Jedi（额外依赖，后续可选）；反射（执行代码副作用）。

### 6.4 动态导入进入 diagnostics 而不是 edges
- **定案【决策】**：dynamic_import 诊断，不生成边；message 带目标（字面量/非字面量）。
- **理由**：目标常无法静态确定；进 diagnostics 提醒缺口；不 silently 遗漏。
- **备选**：解析字面量建边（规则不一致）；忽略（丢信息）。

### 6.5 公共接口保持单一薄函数
- **定案【决策】**：仅暴露 `scan_codebase(root_path: Path) -> dict`。
- **理由**：后端/前端只依赖此函数与返回 schema；内部可自由重构；符合深模块（接口小实现厚）。
- **备选**：暴露内部类型（扩大公共面）；暴露多个扫描函数（诱导依赖内部）。

### 6.6 不过早拆分内部模块，也不预设抽象协议
- **定案【决策】**：扁平 `_*.py` 私有文件，不引入 Protocol/ABC；拆分触发条件**量化**（F/Q9）：`_scanner.py` 超 ~400 行、或编排与 AST 处理无法同屏各读、或测试需绕过编排单独驱动 visitor 时，拆 `_visitor.py`。
- **理由**：原 protocols note 过于抽象易致浅模块；多语言 out of scope；量化触发器防"永远不拆"。
- **备选**：第一版定义 Protocol（违反 YAGNI）；全塞单文件（难维护）。

### 6.7 第一版仅支持 Python
- **定案【决策】**：完全针对 Python AST，不预留多语言接口。
- **理由**：issue #3 明确 Python；过早抽象无真实需求信号；未来可在新 ticket 重设计。
- **备选**：通用 `LanguageParser` 接口（无第二实现验证）；插件机制（超范围）。

### 6.8 类内公开方法不作为独立端口
- **问题（F16）**：grilling 决议引文含"方法"，但第一版是否单列方法端口？
- **定案【决策】**：**不单列**。模块级公开函数/类/`__all__` 是端口；类内公开方法作为类端口的组成部分（由类 signature 体现），不单独进顶层 `ports`。D2 登记对引文的收紧。
- **理由**：深模块原则接口面收窄；类端口的职责已由类的存在表达；单列方法会显著扩大端口数、稀释图谱可读性。
- **备选**：按类端口下枚举公开方法（接口更大，第一版不需要）。

### 6.9 顶层 `ports` 键的两种形态
- **问题（F1）**：issue #2 确认 5 顶层键含 `ports`，但模块已内嵌 ports，重复？
- **定案【决策】**：保留 5 键。模块内嵌 `ports`（供图谱节点渲染）；顶层 `ports` 为**扁平列表**（每条带 `moduleId`，供 AI 描述草稿层/搜索用）。两者由 `_schema` 同一来源生成，保证一致。
- **理由**：issue #2 字面要求 5 键；扁平列表便于按端口消费（AI 草稿、前端筛选）。
- **备选**：丢顶层 `ports`（违反 issue #2 契约）；仅顶层不内嵌（前端渲染要二次 join）。

### 6.10 标准库不产生节点与边
- **问题（F7/Q3）**：标准库进不进 externalModules？
- **定案【决策】**：不进节点、不产生边、文档化忽略。图谱聚焦目标代码库自身。
- **理由**：标准库依赖对架构评审无信号价值；代价用 `Module.stdlibImports` 或独立 ticket 补。
- **备选**：全进 external（图谱噪音）；白名单记录不展示（同"忽略"但冗余）。

## 7. 边界与不变量清单

| # | 不变量 | 防护层 | 依据 |
|---|---|---|---|
| 1 | 一个 `.py` 文件对应一个模块，**未被排除目录过滤** | `_scanner.py` `rglob` + D21 排除集 | D1 / D21 / F6 |
| 2 | 端口只包含公开符号（非下划线开头）；类内方法不单列 | `_ports.py` 过滤 + D2 收紧 | D2 / F16 |
| 3 | 所有**本地** import 产生边、第三方产生 externalModules、标准库忽略 | `_edges` + `_external` 三分支 | D3 / D17 / F7 |
| 4 | 动态导入产生 dynamic_import 诊断 | `_diagnostics` 检测 `__import__`/`importlib.import_module` | D5 / D19 |
| 5 | unresolved_symbol 只在 imports/模块内 defs/builtins 之外产生 | 解析顺序钉死 | D5 / F3 |
| 6 | 输出 JSON 顶层键固定 5 键（modules/ports/edges/externalModules/diagnostics） | `_schema` + JSON Schema 契约 | D7 / D22 / F1 |
| 7 | 不执行被分析代码 | 仅 `ast.parse`，不 import | D4 |
| 8 | 第三方包与标准库可区分 | `_external` 白名单 + 路径匹配 | D10 / D17 |
| 9 | 相对导入基于当前文件所在目录解析（与包根无关） | `_edges` level/current-file 算法 | Q6 / S2 |
| 10 | 本地变量/参数/self/模块内定义不生成边 | 符号表只含模块级 imports + Attribute 三分支 | F3 / F4 |
| 11 | 公共 API 唯一性（scan_codebase） | `__init__.py` 相对导入导出 | D14 / F12 |
| 12 | 内部实现不暴露 | `_` 前缀命名 | D15 |
| 13 | 不预设多语言协议 | 代码无通用 LanguageParser/Protocol | D16 |
| 14 | 单文件语法错误不中断扫描 | `tokenize.open()` + try/except → parse_error | D20 / F5 |
| 15 | 同文件同位置诊断不重复 | 去重键 `(kind, moduleId, line)` | F19 |
| 16 | 多 sites 合并为一条边 | `(source,target,targetPort,kind)` 聚合 | S7 |
| 17 | 无返回注解函数不崩溃 | signature 组装 `if node.returns is not None` | F2 |
| 18 | from-import 子模块优先于 `__init__.py` 端口 | `_edges` 解析顺序 | F17 |

## 8. 测试与验证计划

### 8.1 单元测试

- `test_scan_codebase.py`：`scan_codebase` 返回 dict、5 顶层键完整、可 JSON 序列化。
- `test_ports.py`：`_ports.extract_ports` 公开函数/类/`__all__`；无返回注解（F2）；类内方法不单列（F16）。
- `test_edges.py`：六类边；Attribute 三分支（F4）；from-import 子模块优先（F17）；字符串/Subscript 注解（F18）；builtins/模块内定义不诊断（F3）。
- `test_external.py`：本地/标准库/第三方分类；相对导入（Q6）。
- `test_diagnostics.py`：三类诊断；去重（F19）；message 带目标（Q5）。

### 8.2 fixture 集成测试

- fixture：`parser/tests/fixtures/`（含 sample_pkg / broken_syntax.py / venv_stub）。
- 断言：见 §5.9 每条对应用例。

### 8.3 CLI 测试

- 仓库根 cwd 运行（F11）：`python -m parser parser/tests/fixtures/sample_pkg --output parser/out/graph.json`。
- 验证输出文件存在、JSON 可解析、5 顶层键完整。

### 8.4 提交前自检命令

```bash
cd "C:\Users\liyongquan\agent panel\deep-module-mapper"
python -m pytest parser/tests
python -m parser parser/tests/fixtures/sample_pkg --output parser/out/graph.json
```

### 8.5 评审阻塞项落地（F10/F9）

- **F10**：提交并推送本地 Amendments（`implement-python-parser.md` + 本设计文档 + 评审意见书）→ 更新 issue #3 正文或追加评论登记修订 → 更新 §2.1/§2.2 真值时点。
- **F9**：grilling 决策落档 `wayfinder/grilling-decisions/issue-3-parser-design.md`，随 PR 提交。

## 9. 待评审焦点（Q1-Q9，已裁决）

> 全部裁决已并入 §3/§5/§6（见下表"落地"）。本版起 §9 仅作裁决留痕。

| 焦点 | 裁决 | 落地 |
|---|---|---|
| Q1 相对路径 id + `/` 序列化 | 认可附 2 条件：`resolve()`+`relative_to`、一律 `.as_posix()` | D9 / §5.1 / §6.1 |
| Q2 signature 字符串 vs 结构化参数 | 字符串保留，`Port` 补 `params: list[str]` | D12 / §5.2 / §5.3 |
| Q3 标准库进不进 externalModules | 不进节点不产生边，文档化忽略 | D17 / §5.6 / §6.10 |
| Q4 `__all__` 与下划线冲突 | 显式 `__all__` 优先；re-export 仍纳入且不重复建端口 | D18 / §5.3 |
| Q5 动态导入 severity | 第一版不引入，message 带目标 | D19 / §5.7 |
| Q6 根目录非包时相对导入 | 可行，基准 = 当前文件所在目录 | §5.4 / §5.6 |
| Q7 `_schema.py` 私有 / TypedDict | 保持私有；契约载体 = 独立 JSON Schema | D22 / §5.2 |
| Q8 dict vs 包装对象 | 否决包装类，dict 足够 | §4 / §5.2 |
| Q9 `_scanner` 何时拆 `_visitor` | 触发器量化：超 ~400 行 / 无法同屏各读 / 测试需绕过编排 | §6.6 |

## 10. 评审意见采纳记录

> 评审意见书：`wayfinder/implement-python-parser-评审意见书.md`（2026-08-26，合并两份评审，条件通过）。

| 评审项 | 结论 | 采纳落地 |
|---|---|---|
| F1 顶层键矛盾 | 阻塞，属实 | §5.2 / §6.9 / D7：统一 5 键，顶层 `ports` 扁平列表 |
| F2 `ast.unparse(node.returns)` 崩溃 | 阻塞，实测属实 | §5.3 / 不变量 #17：`if node.returns is not None` 防御 |
| F10 溯源失信 / canonical 分叉 | 阻塞，gh 复核属实 | §8.5：提交推送 + 更新 issue #3 + 更新真值时点 |
| F3 builtins/模块内定义误报 | 重要，属实 | §5.4 解析顺序 / D5 / 不变量 #5、#10 |
| F4 Attribute 三分支 | 重要，属实 | §5.4 / D3 / 不变量 #10 |
| F5 语法错误隔离 | 重要，属实 | D20 / §5.5 / 不变量 #14 / parse_error |
| F6 venv 排除 | 重要，属实 | D21 / §5.5 / 不变量 #1 / fixture |
| F7 标准库归属冲突 | 重要，属实 | D17 / §5.6 / §6.10 / 不变量 #3 |
| F8 dict 契约未钉死 | 重要，属实 | D22 / §5.2 JSON Schema |
| F9 grilling 未落档 | 重要，属实 | §8.5 落档 |
| F11 cwd 矛盾 | 重要，属实 | §5.8 / §8.4 统一仓库根执行 |
| F12 绝对自导入 | 重要，属实 | D15 / §5.5 相对导入 |
| F13 pyproject 缺失 | 重要，属实 | D23 / §5.1 |
| F14 树漏 test_diagnostics | 重要，属实 | §5.1 目录树补入 |
| F15 `__main__.py` 可选矛盾 | 重要，属实 | D23 / §5.8 必选 |
| F16 方法是否端口 | 重要，属实 | §6.8 / D2：不单列，登记收紧 |
| F17 from-import 子模块优先 | 重要，属实 | §5.4 / 不变量 #18 |
| F18 字符串/Subscript 注解 | 重要，实测属实 | §5.4 |
| F19 诊断去重键 | 重要，属实 | §5.2 / 不变量 #15 |
| F20 两遍遍历中间产物 | 重要，属实 | §5.4 RawImport/RawReference 契约 |
| Q1-Q9 裁决 | — | §9 表全部落地 |
| S1/S2/S4/S6/S7/S8 | 建议 | S1/S8 → §4 已知缺口；S2/S4/S6/S7 → 正文并入 |

**推翻项**：无。全部评审发现经独立复核属实。

---

*本文档为 #3 实现基线（v3）。完成评审修订，可进入实现（分支 → 实现 → 测试 → PR → 用户授权 → 合并 → 更新 wayfinder map）。*
