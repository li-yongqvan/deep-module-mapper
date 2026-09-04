# Handoff：#24 v2 实现 —— Archify 模块地图 + 模块内下钻

> **交接日**：2026-09-05（设计+评审在本会话完成，实现交给新会话/执行 agent）
> **执行基线**：分支 `feature/deep-module-review-skill` @ `db6a439`
> **GitHub**：issue #24（v2 区块 + 评审评论已落）

## 0. 必读（按序，实现前读完）

1. `wayfinder/design-doc-deep-module-review-skill.md` **§11–§19** —— v2 权威设计。§14（parser 扩展）与 §15（渲染管线）是实现主体；§19 采纳记录是评审方挑过刺的地方，**每条 F 的落地要求都已写进对应章节，不要凭感觉省略**。
2. `wayfinder/design-doc-deep-module-review-skill-v2-评审意见书.md` —— 看第六节"通过条件清单"，那是验收清单。
3. `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md` v2 节 —— V2-D1~D11 的用户依据。**形态决策不得动**（数据面板/趋势已否决，别加回来）。

## 1. 任务范围（v2 增量，v1 已实现部分不动）

| # | 交付物 | 设计依据 |
|---|---|---|
| ① | **golden fixture 先落**：扩展前对本仓库+sample_pkg 各存一份 5 键输出作 golden 基准（纯附加 pass 的"内容不变"从此可验证） | §14 契约同步清单-4 |
| ② | **parser 扩展**：`scan_codebase` 新增第 6 键 `intra`（模块内函数级调用图）；同步清单四项逐项做（test:22 断言改法、schema.json `intra` 入 required、README/SKILL.md 表述、golden 单测） | §14 全部 |
| ③ | **to_archify.py**：graph+metrics → 主图 architecture IR；确定性布局 + 固定 seed 兜底搜索 + 进程内几何校验（8px）+ 布局缓存 `.last-review/layout.json`；id 映射 `parser__edges` 式拼接 + **碰撞断言** | §15 |
| ④ | **assemble.py**：摘各 deliver 的 `<style>`/`<svg>`（一致性检查，不一致改拼接）、注入面板 DOM + 点击 JS（面板 id ↔ `data-node-id` 映射断言）→ `.last-review/map.html` | §15、§13.4-2 |
| ⑤ | **SKILL.md v2 增补**：触发流程（analyze → AI 泳道标注产 `.last-review/panels/` → deliver ×N → assemble → 提示浏览器打开 map.html）；archify 缺失降级说明；"6 键"表述 | §12、§15 |
| ⑥ | **测试**：§17 全部四组（parser 单测含 shadowing/归属/golden；skill 单测含 id 碰撞/样式兜底/subprocess 编码；端到端；降级 e2e ×3） | §17 |

## 2. 实现顺序（评审约束，勿乱）

**① golden → ③④ 管线（可用现有数据开发）→ ② parser 扩展（最后动，唯一碰契约的改动）→ ⑤ → ⑥**。
理由：评审结语——parser 是唯一影响既有契约的改动，前置 golden 先落再动它。

## 3. 关键事实速查（评审已实测核真）

- **Archify**：`~/.claude/skills/archify/`；命令 `node bin/archify.mjs validate|deliver architecture|workflow <ir> [out] --quality standard|showcase --json`；workflow IR `schema_version: 2`。
- **archify 硬约束**：节点 id `^[a-zA-Z][a-zA-Z0-9_-]*$`；workflow `col ≤ 5`；同泳道同列 <8px 报错；主图 showcase 需零交叉（自动搜索可达，见布局缓存）。
- **subprocess 一律** `encoding="utf-8", errors="replace"`（Windows GBK 教训）。
- **SVG 内嵌多图**：内部 id 加前缀必须用 `(?<=\s)id="..."`（`data-node-id` 尾部会被裸 `id="..."` 正则误伤——v2 原型真实事故）。
- **依赖探测**：`ARCHIFY_DIR` → `~/.claude/skills/archify` → `node --version`，任一缺失走降级（v1 四件套 + 明示，退出码 0）。
- **参考产物**（仅供参考，实现不得依赖其存在）：`C:/Users/liyongquan/AppData/Local/Temp/dmm_v2_demo/`——`extract_intra.py`（intra 提取原型，注意它丢弃顶层调用、无消歧，**别照抄**）、`build_prototype.py`（组装/交互原型）、`prototype.html`（已验收形态）。
- **已知校准点**：本仓库 7 生产模块 42 函数；函数级调用图**无环**，循环=文件级迭代（泳道+解读表达，别硬造环）。

## 4. 红线

- 只读被评审代码；一切产物落 `.last-review/`。
- `scan_codebase` 既有 5 键内容不变（golden 验证）；parser 零第三方依赖。
- 既有测试除 `test_scan_codebase.py:22` 键断言（按 §14 改法）外一律不回归。
- 形态按已验收原型：主图 showcase + 点卡片下钻面板（承诺/泳道图/解读），不加数据面板。

## 5. 完成后

- 跑通 §17 验收清单 + 评审意见书第六节逐项勾选。
- 执行报告追加到 `wayfinder/统筹.md`「报告收件箱」（temporary-coordinator 协议），等统筹处理落地图。
- 向用户演示：对本仓库跑 `/deep-module-review`，浏览器打开 `map.html` 点开面板。
