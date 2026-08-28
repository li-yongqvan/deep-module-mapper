# Deep Module Mapper — Frontend

用 React Flow 渲染后端扫描出的模块依赖图。用户输入本地代码目录路径，前端轮询后端扫描状态，完成后把 Graph JSON 渲染成可缩放、可拖拽的节点图，节点按「深模块」分数显示红绿灯颜色。

**三个视图**（顶部切换）：
- **功能视图（默认）**：把文件级模块按「功能原子」聚合——每个原子 = 一组共同实现某个能力的文件，节点显示**中文名 + 一句话描述**，非开发者也能读懂；噪音文件（tests/fixtures/`__init__.py` 且不在原子内）默认隐藏。详见「功能视图」。
- **现实视图**：文件级模块图（#7），每个 `.py` 文件一个节点。
- **重组视图**：把功能原子拖进/拖出**模块容器**、在模块之间连/删依赖边，重组出理想架构（#10）。详见「重组视图」。

## 功能视图（默认）

### 是什么

- 每个**功能原子**是一个节点：中文名加粗 + 一句话描述，边框颜色 = 原子级深度分（绿深/黄中/红浅）。
- 依赖只在**原子之间**聚合：任一文件依赖另一原子的任一文件，就在两原子间画一条边（label 统一为「依赖」；点边可在右侧查看具体 kind 与调用点）。
- 第三方依赖聚合为单个灰色虚线节点「第三方依赖」，点开可看具体库名。
- 点击原子节点，右侧面板下钻展示**成员文件及其端口**。
- 不在任何原子里的文件（tests/fixtures/`__init__.py` 等）默认不显示；扫描一个 manifest 未覆盖的代码库时，功能视图显示「该代码库暂无功能清单」提示，可切换到现实视图。

### 分组事实源：功能原子清单（manifest）

manifest 由 **AI 聚合 CLI**（issue #11）生成，格式与手工版 drop-in 兼容，可随时重跑替换：

```bash
python -m backend.backend.aggregate <repo> --compare frontend/src/manifest/feature-atoms.json
```

`frontend/src/manifest/feature-atoms.json`

```json
{
  "atoms": [
    {
      "id": "scan-and-parse",
      "name": "扫描并解析代码库",
      "description": "读取代码库，提取每个文件的公开接口与依赖关系",
      "files": ["parser/_scanner.py", "parser/_ports.py"]
    }
  ]
}
```

每个原子：`id`（唯一、稳定）、`name`（中文名）、`description`（一句话描述）、`files`（模块 id 列表，即相对扫描根目录的 posix 路径，与 `graph.modules[].id` 一致）。

**如何编辑**：
- 把一个文件归入某原子：在对应原子的 `files` 里加该路径。
- 新增一个原子：加一个对象（id 唯一、文件路径不与其他原子重复）。
- 仓库自带的 manifest 覆盖全部非噪声生产文件（含 `parser/`、`backend/` 与 `backend/backend/aggregate/*`）。

**注意**：curated manifest 的路径相对仓库根目录——**从仓库根目录扫描**才能命中（例：`deep-module-mapper` 本目录）。扫描子目录得到的是该子目录相对路径，不会命中，此时功能视图为空、需切现实视图。

### 深度分说明

原子级深度分沿用 naive 启发式（`maxLine/portCount`，阈值 50/15），输入 = 原子成员端口并集。deep-module-mapper 自身两个原子均为 **shallow**——小型代码库接口大、实现薄是真实情况；阈值校准留待后续 issue（`src/lib/depthScore.ts` 已注明）。

## 重组视图

自定义画布（界面二）：从功能视图的原子节点出发，把原子拖进/拖出**模块容器**，在模块之间连/删依赖边，重组出理想架构。

**模块** = 容器，可装 1 个或多个功能原子；不在任何显式模块里的原子 = 自己的**单原子模块**。模块显示中文名 + 一个（聚合的）**接口**，依赖边默认由内部原子的依赖自动聚合而来。

用法：
- **新建模块**：工具栏「＋ 新建模块」，再把原子拖进去。
- **拖原子**：把原子 chip 拖进别的模块 = 移入；拖到空白处 = 释放为单原子模块；模块会随原子拖出清空而自动消失。
- **改名 / 改接口**：双击模块标题或接口行，输入后回车。
- **连边**：从一个模块的圆点拖到另一个模块；**删边**：点边 → 右侧详情 → 「删除此边」（或键盘 Delete）。第三方依赖不能作为边的起点。
- **保存 / 加载**：localStorage，**按代码库路径分 key**，刷新/重开浏览器可恢复；**重置为建议分组**：回到 manifest 派生的分组（每个原子单独成模块）。

三条行为兜底（有意为之）：
- **重新扫描**：同路径重扫保留你的分组与未保存编辑（只清理失效原子）；换一个路径扫描则加载该路径已保存的分组，没有就回到建议分组。
- **删除模块**：连带移除它相关的手动边；成员原子会释放为单原子模块。
- **跨标签页不同步**：localStorage 不监听其它标签页的改动；本标签页内保存/加载以本页为准。

## 依赖

- Node.js ≥ 18（开发环境实测 v24.11.1）
- **后端必须运行**（`deep-module-mapper/backend`），默认地址 `http://127.0.0.1:8123`

后端启动（从仓库根目录）：

```bash
python -m pip install -e parser/ -e backend/
python -m uvicorn backend.backend.app:app --reload --port 8123
```

> **注意**：`backend/README.md` 中写的 `backend.app:app` 需在 `backend/` 目录下执行；从仓库根目录启动必须用 `backend.backend.app:app`。
> 长扫描/演示时建议去掉 `--reload`（reload 重启会中断在途扫描）。

## 安装

```bash
cd frontend
npm install
```

## 启动开发服务器

```bash
cd frontend
npm run dev
```

访问 **http://localhost:5175**（端口由 `vite.config.ts` 固定为 5175，非 Vite 默认的 5173）。

## 使用

1. 在顶部输入本地代码目录路径，如 `parser/tests/fixtures/sample_pkg`（相对仓库根目录）或绝对路径。
2. 点击「扫描」，等待状态从 pending → running → done。
3. 扫描完成后画布渲染模块图：
   - **功能视图（默认）**：功能原子节点（中文名 + 描述），第三方依赖聚合为灰色虚线节点，边为原子间聚合边；点击原子下钻成员文件。
   - **现实视图**（顶部切换）：**内部模块**为圆角矩形，边框颜色 = 深度分（绿深/黄中/红浅）；**第三方模块**为灰色虚线框，不评分；**依赖边**带 kind 标签（同模块对的多种依赖已聚合为一条边）。
   - **重组视图**（顶部切换）：功能原子为模块容器内的 chip，可拖进/拖出模块、连/删模块间依赖边（见「重组视图」）。
4. 点击节点/边，右侧面板显示详情（原子成员/模块路径、端口签名、依赖类型与调用点、诊断）。

## 测试

```bash
cd frontend
npm test
```

- `ScanForm.test.tsx` — 表单提交与空路径禁用
- `useScanJob.test.tsx` — 轮询状态机（happy path / 扫描失败 / job 丢失 / graph 失败重试 / 空图）
- `depthScore.test.ts` — naive 深度评分
- `graphToFlow.test.ts` — Graph → React Flow 转换（外部模块、多边聚合、悬空边过滤）
- `featureAtoms.test.ts` — 功能原子 manifest（结构、文件→原子映射、C2 覆盖与噪声排除断言；断言分组无关，AI 重生成不破坏）
- `graphToFeatureFlow.test.ts` — 功能视图转换（映射/噪音过滤/边聚合/第三方聚合/下钻/空图，含真实 fixture）
- `Inspector.test.tsx` — 详情面板下钻（原子/第三方/边/重组模块/手动边/删除边按钮）
- `recompose.derive.test.ts` — 重组派生（初始分组、模块尺寸、子网格、聚合接口、节点派生）
- `recompose.edges.test.ts` — 模块边聚合与增删/隐藏转移表（聚合∪手动−隐藏）
- `recompose.dragDrop.test.ts` — 拖入/拖出/落空白坐标/模块生命周期
- `recompose.persistence.test.ts` — localStorage 保存/加载/校验/sanitize
- `RecomposeModuleNode.test.tsx` / `RecomposeToolbar.test.tsx` — 模块容器与工具栏交互

测试用 [MSW](https://mswjs.io/) 拦截网络请求（`src/test/setup.ts`），不需要后端。

## 构建

```bash
cd frontend
npm run build
```

产物输出到 `frontend/dist/`。

## CORS 说明

后端 CORS 默认 `["*"]`，仅供本地开发。生产环境请用环境变量收紧：

```bash
BACKEND_CORS_ORIGINS="http://localhost:5175" python -m uvicorn backend.backend.app:app --port 8123
```

## 后端地址覆盖

默认 `http://127.0.0.1:8123`，可用环境变量覆盖：

```bash
VITE_BACKEND_URL=http://127.0.0.1:8123 npm run dev
```
