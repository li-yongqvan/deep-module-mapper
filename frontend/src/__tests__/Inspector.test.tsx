/**
 * Inspector drill-down render tests (issue #8 spec criterion 8 — the atom
 * drill-down UI branch was previously untested).
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import Inspector, {
  type AtomNodeSelection,
  type ExternalNodeSelection,
  type EdgeSelection,
  type RecomposedModuleSelection,
} from '../components/Inspector';

describe('Inspector', () => {
  it('renders an atom drill-down: name, description, member files with ports', () => {
    const selection: AtomNodeSelection = {
      type: 'node',
      kind: 'atom',
      id: 'atom:scan-api',
      label: '扫描 API 服务',
      name: '扫描 API 服务',
      description: '把扫描功能封装成 HTTP 接口，管理扫描任务与结果',
      files: ['backend/backend/app.py'],
      modules: [
        {
          id: 'backend/backend/app.py',
          path: 'backend/backend/app.py',
          ports: [
            { kind: 'function', name: 'route', line: 40, signature: 'route()', params: [] },
          ],
        },
      ],
      score: 'shallow',
      portCount: 1,
    };
    render(
      <Inspector selection={selection} graphDiagnostics={[]} onClose={() => {}} />,
    );
    expect(screen.getByText('扫描 API 服务')).toBeInTheDocument();
    expect(screen.getByText(/把扫描功能封装成 HTTP 接口/)).toBeInTheDocument();
    expect(screen.getByText(/成员文件（1）/)).toBeInTheDocument();
    expect(screen.getByText('backend/backend/app.py')).toBeInTheDocument();
    expect(screen.getByText('route()')).toBeInTheDocument();
    expect(screen.getByText('shallow')).toBeInTheDocument();
  });

  it('renders the aggregated third-party drill-down with concrete library names', () => {
    const selection: ExternalNodeSelection = {
      type: 'node',
      kind: 'external',
      id: 'ext:third-party',
      label: '第三方依赖',
      externalNames: ['pydantic', 'starlette.applications'],
    };
    render(
      <Inspector selection={selection} graphDiagnostics={[]} onClose={() => {}} />,
    );
    expect(screen.getByText('第三方依赖')).toBeInTheDocument();
    expect(screen.getByText('pydantic')).toBeInTheDocument();
    expect(screen.getByText('starlette.applications')).toBeInTheDocument();
  });

  it('renders edge drill-down with kinds and call sites', () => {
    const selection: EdgeSelection = {
      type: 'edge',
      source: 'atom:scan-api',
      target: 'atom:scan-and-parse',
      label: 'call, from_import',
      data: {
        kinds: ['call', 'from_import'],
        rawEdges: [
          {
            source: 'backend/backend/scanner.py',
            target: 'parser/__init__.py',
            kind: 'call',
            sites: [{ line: 16 }],
          },
          {
            source: 'backend/backend/scanner.py',
            target: 'parser/__init__.py',
            kind: 'from_import',
            sites: [{ line: 7 }],
          },
        ],
      },
    };
    render(
      <Inspector selection={selection} graphDiagnostics={[]} onClose={() => {}} />,
    );
    expect(screen.getByText('atom:scan-api → atom:scan-and-parse')).toBeInTheDocument();
    expect(screen.getByText(/类型：call, from_import/)).toBeInTheDocument();
    expect(screen.getByText(/from_import @7/)).toBeInTheDocument();
  });

  it('renders a manual edge without rawEdges and does not throw (#1)', () => {
    const selection: EdgeSelection = {
      type: 'edge',
      id: 'manual-edge-mod:a->mod:b',
      source: 'mod:a',
      target: 'mod:b',
      label: '手动',
      data: { manual: true, kinds: [], rawEdges: [], displayLabel: '手动' },
    };
    render(
      <Inspector selection={selection} graphDiagnostics={[]} onClose={() => {}} />,
    );
    expect(screen.getByText(/手动添加的依赖（无底层调用点）/)).toBeInTheDocument();
  });

  it('shows a delete-edge button when onDeleteEdge is provided and clicks route the edge id (#3)', () => {
    const onDeleteEdge = vi.fn();
    const selection: EdgeSelection = {
      type: 'edge',
      id: 'module-edge-mod:a->mod:b',
      source: 'mod:a',
      target: 'mod:b',
      label: 'call',
      data: {
        kinds: ['call'],
        rawEdges: [
          { source: 'p/a.py', target: 'p/b.py', kind: 'call', sites: [{ line: 3 }] },
        ],
      },
    };
    render(
      <Inspector
        selection={selection}
        graphDiagnostics={[]}
        onClose={() => {}}
        onDeleteEdge={onDeleteEdge}
      />,
    );
    fireEvent.click(screen.getByText('删除此边'));
    expect(onDeleteEdge).toHaveBeenCalledWith('module-edge-mod:a->mod:b');
  });

  it('renders a recomposed module drill-down: name, interface, members, ports, score', () => {
    const selection: RecomposedModuleSelection = {
      type: 'node',
      kind: 'recomposeModule',
      id: 'mod:1',
      label: '目标模块',
      name: '目标模块',
      description: '整合扫描与 API 服务',
      memberAtomNames: ['扫描并解析代码库', '扫描 API 服务'],
      memberFileCount: 12,
      ports: [
        { kind: 'function', name: 'scan', line: 18, signature: 'scan(root_path) -> dict', params: [] },
      ],
      score: 'moderate',
    };
    render(
      <Inspector selection={selection} graphDiagnostics={[]} onClose={() => {}} />,
    );
    expect(screen.getByText('目标模块')).toBeInTheDocument();
    expect(screen.getByText('整合扫描与 API 服务')).toBeInTheDocument();
    expect(screen.getByText(/1 个端口，12 个文件/)).toBeInTheDocument();
    expect(screen.getByText('扫描并解析代码库')).toBeInTheDocument();
    expect(screen.getByText('scan(root_path) -> dict')).toBeInTheDocument();
    expect(screen.getByText('moderate')).toBeInTheDocument();
  });
});
