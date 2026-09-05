# Deep Module Mapper → `/deep-module-review`

> 从独立 Web 应用迁移而来的 **Claude Code skill**（issue #24）。原 `frontend/`、
> `backend/` 已删除（git tag `archive/app-before-skill-migration` 可回查）。

对一个 **Python 代码库**做一次只读的「深模块评审」：解析模块与依赖 → 生成指标
与 **Archify 模块地图**（主图 + 点卡片下钻的模块内函数泳道图 + AI 解读）→
Claude 主动给出结构化结论。Archify/node 不可用时降级为 v1 SVG Artifact。

## 使用

在 Claude Code 中，评审当前目录：

```
/deep-module-review
```

或指定要评审的仓库：

```
/deep-module-review C:/path/to/another/python/repo
```

产物落在 `.claude/skills/deep-module-review/.last-review/`（已 gitignore）：
v2 为 `map.html`（浏览器打开，单文件模块地图）+ 中间产物；降级为 v1 四件套
`graph.json`、`metrics.json`、`digest.json`、`diagram.svg`。

## 它怎么工作

```
parser/scan_codebase(仓库, exclude_dirs=…)
   → graph.json           原始扫描图（6 顶层键：5 既有键 + intra 函数级调用图）
   → metrics.py           depthScore(50/15) · 边聚合 · SCC 环检测 · 孤儿三分类
   → digest.py            截断阶梯摘要（迁移自旧 backend/aggregate/digest.py）
   → to_archify.py        graph+metrics → 主图 architecture IR（确定性布局，
                          固定 seed 兜底搜索 + 布局缓存 layout.json + id 碰撞断言）
   → AI 标注 panels/      每个生产模块：泳道/承诺/解读（SKILL.md 产出规范）
   → assemble.py          archify deliver ×(1 主图 + N 面板) → 合成 map.html
   → diagram.py           v1 内联 SVG（降级路径 / 兜底）
```

- 模块 = 一个 `.py` 文件（parser 语义）。评审范围 = **生产模块**（排除
  `tests/`、`fixtures/`、`__init__.py` 门面；`__init__` 重导出会把消费方依赖指回
  真正生产者）。
- `intra` 键（v2，#24 §14）：每模块函数级调用图 `{funcs, calls}`。类 = 单节点
  （方法不展开，V2-D6）；顶层调用宿主为伪节点 `<module>`；回调引用（`key=f`）
  入边；同名遮蔽（局部/参数/导入/内置名）不产生幻边。扩展为纯附加 pass，
  既有 5 键内容不变（golden 测试逐字节验证）。
- 深度评分沿用 `depthScore.ts` 阈值：`ratio = 最大端口行号 / 端口数`，DEEP≥50、
  MODERATE≥15，0 端口判 shallow。
- v1/v2 图均不渲染外部依赖节点（D7），第三方依赖只在 metrics 汇总。
- Archify 依赖探测：`ARCHIFY_DIR` → `~/.claude/skills/archify` → `node --version`；
  任一缺失即降级 v1 四件套并明示（退出码 0，不是错误）。
- 主图质量档位：先验 showcase、不过降 standard（单次降档）。**多模块仓库
  （依赖成簇）默认预期即 standard**——正交路由器障碍感知，密集依赖簇实测过不了
  showcase 检查；只影响主图连线观感，不影响图内数据正确性；下钻面板固定
  standard，不受主图档位影响。

## 脚本

```bash
python -m pytest parser/tests -q                                        # parser 回归（含 intra/golden）
python -m pytest .claude/skills/deep-module-review/tests -q             # skill 单测
python .claude/skills/deep-module-review/scripts/analyze.py <repo>      # 端到端（v1 四件套）
python .claude/skills/deep-module-review/scripts/to_archify.py          # 主图 IR（需 archify）
python .claude/skills/deep-module-review/scripts/assemble.py           # 合成 map.html（需 archify + panels/）
```

依赖：Python ≥ 3.10 标准库，零第三方运行时依赖；v2 渲染另需
[Archify](https://github.com/tt-a1i/archify)（`~/.claude/skills/archify`）与 node
（可选外部增强，进程调用，非 import 依赖）。

## 目录

```
parser/                                     # 纯 Python AST 解析器（v2 加 intra 提取）
.claude/skills/deep-module-review/          # 本 skill
    SKILL.md
    scripts/{analyze,metrics,digest,diagram,to_archify,assemble,archify_env}.py
    scripts/template.html                   # v1 降级 Artifact 模板
    tests/
wayfinder/                                  # 项目地图与设计/评审归档（含 handoff 与决策）
```

## 项目治理

- 项目状态地图：`wayfinder/map.md`（镜像 GitHub issue #1）。
- 本迁移的基线：`wayfinder/design-doc-deep-module-review-skill.md`（含 v2 §11–§19）
  + 两份评审意见书 + `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md`。
- 执行说明：`wayfinder/handoff-deep-module-review-skill-v2.md`。
