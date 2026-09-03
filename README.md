# Deep Module Mapper → `/deep-module-review`

> 从独立 Web 应用迁移而来的 **Claude Code skill**（issue #24）。原 `frontend/`、
> `backend/` 已删除（git tag `archive/app-before-skill-migration` 可回查）。

对一个 **Python 代码库**做一次只读的「深模块评审」：解析模块与依赖 → 生成指标与
架构图 → Claude 主动给出结构化结论（深模块对齐性 / 依赖简洁性 / 模块深度分布 /
关键发现 / 建议），以 HTML Artifact 呈现。

## 使用

在 Claude Code 中，评审当前目录：

```
/deep-module-review
```

或指定要评审的仓库：

```
/deep-module-review C:/path/to/another/python/repo
```

每次输出四个临时文件到 `.claude/skills/deep-module-review/.last-review/`（已
gitignore）：`graph.json`、`metrics.json`、`digest.json`、`diagram.svg`。

## 它怎么工作

```
parser/scan_codebase(仓库, exclude_dirs=…)
   → graph.json           原始扫描图（5 顶层键）
   → metrics.py           depthScore(50/15) · 边聚合 · SCC 环检测 · 孤儿三分类
   → digest.py            截断阶梯摘要（迁移自旧 backend/aggregate/digest.py）
   → diagram.py           grid 布局内联 SVG（deep=绿 / moderate=琥珀 / shallow=红）
   → template.html        结论置顶的 Artifact 模板
```

- 模块 = 一个 `.py` 文件（parser 语义）。评审范围 = **生产模块**（排除
  `tests/`、`fixtures/`、`__init__.py` 门面；`__init__` 重导出会把消费方依赖指回
  真正生产者）。
- 深度评分沿用 `depthScore.ts` 阈值：`ratio = 最大端口行号 / 端口数`，DEEP≥50、
  MODERATE≥15，0 端口判 shallow。
- v1 图不渲染外部依赖节点（D7），第三方依赖只在 metrics 汇总。

## 脚本

```bash
python -m pytest parser/tests -q                                        # parser 39 回归
python -m pytest .claude/skills/deep-module-review/tests -q             # skill 单测
python .claude/skills/deep-module-review/scripts/analyze.py <repo>      # 端到端
```

依赖：Python ≥ 3.10 标准库，零第三方运行时依赖。

## 目录

```
parser/                                     # 纯 Python AST 解析器（保留，#24 仅加 exclude_dirs）
.claude/skills/deep-module-review/          # 本 skill
    SKILL.md
    scripts/{analyze,metrics,digest,diagram}.py + template.html
    tests/
wayfinder/                                  # 项目地图与设计/评审归档（含 handoff 与 D1–D7）
```

## 项目治理

- 项目状态地图：`wayfinder/map.md`（镜像 GitHub issue #1）。
- 本迁移的基线：`wayfinder/design-doc-deep-module-review-skill.md` + `-评审意见书.md`
  + `wayfinder/grilling-decisions/deep-module-review-skill-decisions.md`（D1–D7）。
- 执行说明：`wayfinder/handoff-deep-module-review-skill.md`。
