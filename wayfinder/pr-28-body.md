Closes #28（评审鲁棒性三项，2026-09-06 狗粮暴露）。

## 子项 A：零模块守卫（`analyze.py`）

对不含任何 `.py` 的仓库（实测 ai-forum，Go+Vue），原先静默产出 0 模块空 map.html（318KB），用户无从得知扫了个寂寞。现 `graph.modules` 为空时抛出明确错误并 exit 1：「不是 Python 项目 / 没有 .py 文件 + 当前仅覆盖 Python（#30 多语言前的短期替身）」，**零产物写出**。

实测：`analyze.py <ai-forum>` → `analyze: error: no Python modules found under ... This skill currently covers Python only (#30 tracks more languages). No artefacts written.`，exit=1。

## 子项 B：星号导入诊断聚合（`parser/_scanner.py` + 新诊断类型 `star_import_unresolved`）

`from x import *` 不绑定名字，原先每个使用点各报一条 `unresolved_symbol`——QuickCut 586 条、you-get 1626 条，真实信号被淹没。现含星号导入的模块把**引用侧**未解析**按每条星号导入聚合为一条**（锚定在 import 行，附模块级计数 + 至多 5 个命名样本）：

- 措辞保留诚实语义「may come from star import of ...」——静态无法归属到具体哪条星号导入，根治在姊妹票 **#29**（两趟解析）；
- import 自身的未解析、`dynamic_import` 等其它诊断、不含星号导入的模块：行为不变（golden 5 键逐字节一致）；
- `schema.json` 枚举同步新增 `star_import_unresolved`。

实测复扫：QuickCut **586 → 4**（4 条 `import *`）；you-get **1626 → 105** 聚合 + 48 条真未解析按点保留（非星号导入模块的真动态注入，维持「宁缺勿幻」）。

## 子项 C：扫描 stderr 警告隔离（`parser/_scanner.py` + `parser/_edges.py`）

`ast.parse` 会编译被扫源码，其 SyntaxWarning（如正则 `\.` 非法转义）漏到 skill 会话 stderr（QuickCut 12 条、you-get 4 条）。模块体解析与字符串注解解析两处均以 `warnings.catch_warnings` 隔离——调用方即使 `-W error::SyntaxWarning` 扫描也不中断。

## 验证

- 135 测试全绿（基线 126 + 新增 9：星号聚合 ×4 / 警告隔离 ×2 / 零模块守卫 ×3）；
- golden 5 键逐字节不变；
- 三狗粮仓库实测如上。

## 备注

- 双份维护：agent panel skill 副本的 `analyze.py` 已手动同步（parser 经 sibling 解析共享，无需同步）；#31 宪法化瘦身在途，本 PR 未触碰 SKILL.md。
