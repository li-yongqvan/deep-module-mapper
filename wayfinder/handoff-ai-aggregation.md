# Handoff: AI aggregation — local model clusters files into functional atoms

**Ticket**: GitHub issue #11 — https://github.com/li-yongqvan/deep-module-mapper/issues/11  
**Role**: **执行 Agent（Worker）** — 本会话是一个执行分支  
**Mission**: Replace the hand-maintained functional-atom manifest with AI aggregation — the local model reads file contents and decides which files together implement one capability, producing the functional atoms. **AI proposes, human disposes.**

## 你的身份与边界（重要，先读）

你是**执行 Agent**，不是统筹方。只完成本 ticket，开 PR，汇报。

**你做**：实现、写测试、开 PR、汇报。
**你不做**：不更新 `wayfinder/map.md`、不创建/改写/关闭 issue（含本 ticket）、不分配后续 ticket、不规划排期、不擅自合并 PR/关闭 issue/删除分支/push 到 main。
**何时停下请示**：范围不清、需要新决策、需要跨 ticket 改动时，停下来问统筹方/用户。

## 关键事实（统筹方已核实，不要假设）

1. **manifest 契约** = `FeatureAtom { id, name, description, files }`，位于 `frontend/src/manifest/feature-atoms.json` + `featureAtoms.ts`。AI 聚合输出必须是这个格式的 drop-in 替换。
2. **后端没有既有 AI provider 接口**。原 #8 的「backend AI endpoints」（descriptions/review）范围已被移除，后端只有 scan/status/graph 三个端点。本 ticket 必须**新建** AI provider 抽象，不是复用。
3. **本地模型**：Ollama `my-assistant`（qwen3:8b）@ `127.0.0.1:11434`。**prompt 纪律弱**——实测它会展开解释而非只说一句，可能不输出合法 JSON。必须设计强结构 prompt + retry/repair。
4. 北极星：AI 提议，人定夺。聚合输出喂给 #8 功能视图 / #10 重组画布已消费的 manifest 格式。

## Context pointers

Read these before writing code:

- `deep-module-mapper/UBIQUITOUS_LANGUAGE.md` — domain terms.
- `frontend/src/manifest/featureAtoms.ts` + `feature-atoms.json` — the manifest contract (drop-in target).
- `frontend/src/lib/graphToFeatureFlow.ts` — how the manifest is consumed today.
- `backend/backend/app.py` — existing Starlette app; only scan/status/graph endpoints exist.
- `backend/backend/scanner.py` — how `scan_codebase` is invoked today.
- `deep-module-mapper/wayfinder/handoff-issue-8-feature-view-complete.md` — manifest origin + feature view.
- `deep-module-mapper/wayfinder/handoff-issue-5-complete.md` — backend API contract.
- `C:\Users\liyongquan\.claude\projects\C--Users-liyongquan-agent-panel\memory\llm-agent-env-quirks.md` — local-model quirks (Ollama path, weak prompt discipline).

## Steps

### 1. Design the aggregation architecture

Decide and state in the PR: where does AI aggregation run?
- **Option A**: a backend endpoint (e.g. `POST /api/aggregate`) the frontend calls after a scan.
- **Option B**: a CLI/script the user runs, producing a manifest file the frontend loads.

Whichever you choose, the **output must be a drop-in replacement** for `feature-atoms.json` (same `FeatureAtom` shape). Do not change the frontend contract.

**Done when**: you can articulate the architecture and it produces manifest-shaped output.

### 2. Create the AI provider abstraction (NEW)

Build a small internal interface for the Ollama call — endpoint, model name, prompt, and retry behind one interface — so providers can be swapped later. Do not reuse (there is nothing to reuse); create it.

**Done when**: you can call the provider with a prompt and get a text/JSON response back, and swapping the provider later is a one-place change.

### 3. Engineer the aggregation prompt (the hard part)

The model (`my-assistant`, qwen3:8b) has weak instruction discipline — it expands instead of obeying, and may not emit valid JSON. Design the prompt defensively:

- **Strong structure**: tell it exactly what to output (a JSON manifest of functional atoms).
- **Few-shot examples**: give it a worked example of a small codebase → manifest.
- **JSON schema**: constrain the output shape; instruct it to output only JSON.
- **Retry/repair**: if output is not valid JSON, retry with a repair prompt, or degrade.

Feed it the scanned Graph (modules + ports) and enough file content to judge grouping.

**Done when**: for a small fixture, the model reliably produces a valid manifest (valid JSON, valid `FeatureAtom` shape) — or reliably falls back when it can't.

### 4. Implement graceful fallback

If the model is unreachable, times out, or returns malformed output (after retries), **fall back to the hand-maintained manifest** (the existing `feature-atoms.json`) and surface a diagnostic so the human knows AI aggregation failed.

**Done when**: killing the Ollama endpoint (or feeding garbage) produces the hand-maintained manifest + a visible diagnostic, not a crash.

### 5. Add tests

Mock/stub the model call. Cover:
- happy path: model returns a valid manifest → aggregation succeeds.
- malformed output → retry → repair or degrade.
- model unreachable → fallback to hand-maintained manifest + diagnostic.
- output format is a valid drop-in (same `FeatureAtom` shape).

**Done when**: `pytest backend/tests` (or the equivalent) passes with the model stubbed; `npm test`/`npx tsc --noEmit` still pass if the frontend is touched.

### 6. Update README

Document: model config (endpoint, model name, prompt), how to run aggregation, what the fallback behavior is.

**Done when**: a new reader can configure and run AI aggregation from README alone.

## Decisions to make in the PR

- Architecture: backend endpoint vs CLI/script (Option A vs B).
- Where the AI provider interface lives (backend or a shared module).
- Retry/repair policy (attempts, repair prompt shape).
- How fallback is surfaced (diagnostic format).

## Red lines

- Do **not** modify `parser` public API (`scan_codebase`).
- Do **not** modify the existing `/api/scan`, `/api/scan/:jobId/status`, `/api/scan/:jobId/graph` endpoints (if you add `/api/aggregate`, add it — don't change the scan endpoints).
- Do **not** change the manifest contract the frontend consumes (drop-in only).
- Do **not** implement the canvas review endpoint (later ticket).
- Do **not** merge, close issues, or delete branches without explicit user approval.

## Worktree discipline

This repo may have parallel Agents. Before you start:

1. Confirm you are in a dedicated git worktree (not the main checkout).
2. Run `git status --short` and `git branch --show-current`.
3. Do not operate in another Agent's worktree.

See [[parallel-session-worktree-discipline]].

## Useful skills

- `/tdd` — test the fallback/retry logic first.
- `/codebase-design` — keep the provider abstraction clean.
- `/prototype` — quick Ollama prompt spike before committing to the design.

## Report back with

1. One-sentence summary of what changed.
2. Files modified and PR link.
3. Verification results (test output; one real Ollama aggregation run showing a valid manifest for a fixture).
4. Next step or blocker.
5. Any decision that still needs the user.
