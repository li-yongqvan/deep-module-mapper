## 决议记录（implementation，PR #32）

三子项均已实现并验证，待 PR #32 合并后本票经 `Closes #28` 自动关闭。

**A 零模块守卫**（`analyze.py`）：`graph.modules` 为空 → 明确报错 exit 1（不是 Python 项目 / 当前仅覆盖 Python——#30 多语言前的短期替身），零产物写出。实测 ai-forum：报错文案清晰、无空 map.html。
**B 星号导入聚合**（parser，新诊断 `star_import_unresolved`）：含 `import *` 的模块把引用侧未解析按每条星号导入聚合为一条（锚定 import 行 + 模块级计数 + ≤5 个命名样本），措辞保留 may-come-from 诚实语义（静态无法归属，根治在 #29）。import 自身未解析与无星号导入模块行为不变，golden 5 键逐字节一致，schema.json 枚举已同步。实测：QuickCut 586→4，you-get 1626→105（另 48 条真未解析按点保留）。
**C 警告隔离**（parser）：模块体解析 + 字符串注解解析两处 `warnings.catch_warnings` 隔离；调用方 `-W error::SyntaxWarning` 下扫描也不中断。实测 QuickCut 不再泄漏。

验证：135 测试全绿（+9 新）；三狗粮仓库实测如上。agent panel skill 副本 `analyze.py` 已手动同步。
