/**
 * Inspector drill-down render tests (issue #8 spec criterion 8 — the atom
 * drill-down UI branch was previously untested).
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Inspector, {
  type AtomNodeSelection,
  type ExternalNodeSelection,
  type EdgeSelection,
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
});
