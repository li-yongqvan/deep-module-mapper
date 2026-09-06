# Handoff：#31 SKILL.md 宪法化瘦身 —— 删 runbook + 脚本自描述化

> **交接日**：2026-09-06（统筹会话备稿，实现交给新会话/执行 agent）
> **票**：GitHub issue #31（含逐段审计表 = 本任务权威需求）
> **基线**：master @ `b9010d3`（PR #32 合并后，工作区干净）
> **手术对象**：`.claude/skills/deep-module-review/SKILL.md`（当前 144 行）

## 0. 必读（按序）

1. `gh issue view 31` 正文 —— **权威需求**：逐段审计表（可删 vs 必须留）、方向四条、验收方向三条。
2. `.claude/skills/deep-module-review/SKILL.md` 现状全文 —— 手术对象，先逐段对照审计表打草稿再动。
3. 本 handoff §3 关键事实 —— 都是本会话实测过的真值。

## 1. 任务范围（三个交付，勿扩）

| # | 交付物 | 依据 |
|---|---|---|
| ① | **SKILL.md 瘦身**：按 issue #31 审计表删 runbook、留宪法；剩余内容必须全部落在「好的标准 / 红线 / 产出契约」三类 | issue #31 审计表 |
| ② | **脚本自描述化**：`analyze.py` stdout 在现有 JSON 之外打印**下一步指引**（如「archify 可用 → 跑 to_archify.py → 为 N 个生产模块写 panels/<id>.json → 跑 assemble.py → 提示浏览器打开 map.html」）；`assemble.py:323` 报错文案里的「SKILL.md step」引用同步改为脚本自述 | issue #31 方向 3 |
| ③ | **双份同步**：改完后 `agent panel/.claude/skills/deep-module-review/` 副本与仓库副本恢复逐字节一致（diff 为空） | map.md Notes 双份维护 |

## 2. 宪法 vs runbook 判定表（摘自 issue #31，逐条对照落地）

| 段落 | 判定 |
|---|---|
| 触发与用法（依赖/探测） | ✅ 必须留——运行契约 |
| §1 命令 + 输出文件表格 + intra 字段解释 | ⚠️ 大半可删——留一句「入口 analyze.py」即可 |
| §2A ②④ 命令 | ⚠️ 可删——纯步骤 |
| §2A ③ 面板标注规范 | 🔀 混合：格式细节（列号 0-5、id pattern）assemble.py 已断言，属重复可瘦；「每个函数覆盖、不得虚构、有环指回路没环别硬造」是产出质量红线，必须留 |
| §2A ⑤ 交付 + §2B 降级契约 | ✅ 必须留（map.html 非 Artifact、降级明示）；模板占位符名可瘦 |
| §评审准则 + §红线 | ✅ 必须留——宪法本体 |

## 3. 关键事实速查（本会话实测）

- **现状 144 行**；仓库副本与 agent panel 副本**当前逐字节一致**（③做完后必须回到这个状态）。
- **无测试读 SKILL.md 内容**——`tests/conftest.py` 只取 `SKILL_DIR` 路径；断言本就在 `assemble.py`。这是「瘦 SKILL.md 不破坏测试」的机理，无需改任何测试。
- **analyze.py stdout 现状** = 一行紧凑 JSON（archify 探测 + graph/metrics/digest/diagram 四路径），**无下一步指引** → ②的主要工作量在这里。注意 stdout 被 e2e/单测以 JSON 解析（`test_skill.py`/`test_e2e.py`），加指引时保持 JSON 可解析（指引放新增字段或 stderr，先读测试再定）。
- **to_archify.py / assemble.py stdout 已是 JSON**；assemble 报错已带指引性文案（`:323` 提到 "SKILL.md step: AI writes panels/*.json first"——瘦身后这句要改成不依赖 SKILL.md 章节的自述）。
- **frontmatter `description` = 触发契约**：可精简，但「只读」「`.py` = 模块」「map.html 下钻 / 无 Archify 降级 v1 SVG」三个触发语义不能丢。
- PR #32 合并时**特意未触碰 SKILL.md**（`#31 在途` 备注），当前无冲突隐患。
- 宪法方向与已拍板 skill 级原则「**普查优先、遇障降级策展**」一致——瘦身是更信任 AI 判断，不是放松标准。

## 4. 红线

- 宪法三段（评审哲学 / 红线 / 产出契约）**只加强不削弱**；v1 降级必须明示的协议一句不能删。
- 面板质量红线（每函数覆盖、不得虚构函数/调用边、有环指回路没环别硬造）在 SKILL.md 与 assemble.py 报错文案**至少一处保留**，最好两处。
- 不动 `parser/` 逻辑；`python -m pytest parser/tests .claude/skills/deep-module-review/tests -q` **135 全绿**不得回归。
- 方向已拍板（issue #31 四条），**不要扩成「重写 skill / 改交互形态」**。

## 5. 验收（照 issue #31 验收方向逐条核）

1. SKILL.md 行数显著下降，剩余内容全部属「好的标准 / 红线 / 产出契约」三类（逐段能对回审计表判定）；
2. **全新会话**仅凭瘦身后 SKILL.md + 脚本 stdout 指引能完整跑通 v2 流程（e2e 实测：对本仓库跑 analyze → 到 map.html 产出；顺带核对 v1 降级文案仍正确）；
3. 135 测试全绿；
4. 仓库副本 vs agent panel 副本 diff 为空。

## 6. 完成后（走协议，别学 #28）

1. 开 PR（`docs(skill)` 或 `refactor(skill)`，正文含 `Closes #31`），**不自行合并**。
2. **执行报告追加到 `wayfinder/统筹.md`「报告收件箱 → 待处理」**（格式见统筹文件模板）——#28 曾漏报导致统筹靠仓库痕迹倒查，本次务必走协议。
3. 向用户演示：对本仓库跑 `/deep-module-review`，浏览器打开 map.html 下钻一个面板，确认 AI 仅凭瘦身后说明 + stdout 指引走完全程。
