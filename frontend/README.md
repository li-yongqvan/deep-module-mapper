# Deep Module Mapper — Frontend（现实视图）

用 React Flow 渲染后端扫描出的模块依赖图。用户输入本地代码目录路径，前端轮询后端扫描状态，完成后把 Graph JSON 渲染成可缩放、可拖拽的节点图，节点按「深模块」分数显示红绿灯颜色。

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
   - **内部模块**：圆角矩形，边框颜色 = 深度分（绿深/黄中/红浅）。
   - **第三方模块**：灰色虚线框，不评分。
   - **依赖边**：带 kind 标签（同模块对的多种依赖已聚合为一条边）。
4. 点击节点/边，右侧面板显示详情（模块路径、端口签名、依赖类型与调用点、诊断）。

## 测试

```bash
cd frontend
npm test
```

- `ScanForm.test.tsx` — 表单提交与空路径禁用
- `useScanJob.test.tsx` — 轮询状态机（happy path / 扫描失败 / job 丢失 / graph 失败重试 / 空图）
- `depthScore.test.ts` — naive 深度评分
- `graphToFlow.test.ts` — Graph → React Flow 转换（外部模块、多边聚合、悬空边过滤）

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
