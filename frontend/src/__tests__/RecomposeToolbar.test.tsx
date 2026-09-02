import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import RecomposeToolbar from '../components/RecomposeToolbar';
import type { ModuleFindings } from '../lib/recompose/detect';

function makeFindings(overrides: Partial<ModuleFindings> = {}): ModuleFindings {
  return {
    cycles: [],
    orphans: [],
    thirdPartyOnly: [],
    count: { cycles: 0, orphan: 0, thirdPartyOnly: 0 },
    byModule: new Map(),
    ...overrides,
  };
}

describe('RecomposeToolbar', () => {
  it('renders all four actions and fires their callbacks', () => {
    const onCreateModule = vi.fn();
    const onSave = vi.fn();
    const onLoad = vi.fn();
    const onReset = vi.fn();

    render(
      <RecomposeToolbar
        onCreateModule={onCreateModule}
        onSave={onSave}
        onLoad={onLoad}
        onReset={onReset}
      />,
    );

    fireEvent.click(screen.getByText('＋ 新建模块'));
    expect(onCreateModule).toHaveBeenCalled();

    fireEvent.click(screen.getByText('保存'));
    expect(onSave).toHaveBeenCalled();

    fireEvent.click(screen.getByText('加载'));
    expect(onLoad).toHaveBeenCalled();

    fireEvent.click(screen.getByText('重置为建议分组'));
    expect(onReset).toHaveBeenCalled();
  });

  it('shows transient feedback when provided', () => {
    render(
      <RecomposeToolbar
        onCreateModule={() => {}}
        onSave={() => {}}
        onLoad={() => {}}
        onReset={() => {}}
        feedback="已保存"
      />,
    );
    expect(screen.getByText('已保存')).toBeInTheDocument();
  });

  it('renders diagnostic counts', () => {
    const diagnostics = makeFindings({
      cycles: [
        {
          code: 'cycle/scc',
          severity: 'error',
          subject: { moduleIds: ['mod:a'] },
          message: 'cycle',
        },
      ],
      orphans: [
        {
          code: 'orphan/isolated',
          severity: 'warning',
          subject: { moduleIds: ['mod:b'] },
          message: 'orphan',
        },
      ],
      thirdPartyOnly: [
        {
          code: 'orphan/third-party-only',
          severity: 'warning',
          subject: { moduleIds: ['mod:c'] },
          message: 'tp',
        },
      ],
      count: { cycles: 1, orphan: 1, thirdPartyOnly: 1 },
    });
    render(
      <RecomposeToolbar
        onCreateModule={() => {}}
        onSave={() => {}}
        onLoad={() => {}}
        onReset={() => {}}
        diagnostics={diagnostics}
      />,
    );
    expect(screen.getByText('在环里 1')).toBeInTheDocument();
    expect(screen.getByText('孤立 1')).toBeInTheDocument();
    expect(screen.getByText('仅连第三方 1')).toBeInTheDocument();
  });

  it('expands a list and calls onSelectModule when an item is clicked', () => {
    const onSelectModule = vi.fn();
    const diagnostics = makeFindings({
      cycles: [
        {
          code: 'cycle/scc',
          severity: 'error',
          subject: { moduleIds: ['mod:a'] },
          message: 'cycle',
        },
      ],
      count: { cycles: 1, orphan: 0, thirdPartyOnly: 0 },
    });
    render(
      <RecomposeToolbar
        onCreateModule={() => {}}
        onSave={() => {}}
        onLoad={() => {}}
        onReset={() => {}}
        diagnostics={diagnostics}
        onSelectModule={onSelectModule}
      />,
    );
    fireEvent.click(screen.getByText('在环里 1'));
    const item = screen.getByText('[在环里] mod:a');
    expect(item).toBeInTheDocument();
    fireEvent.click(item);
    expect(onSelectModule).toHaveBeenCalledWith('mod:a');
  });

  it('disables pills with zero count', () => {
    render(
      <RecomposeToolbar
        onCreateModule={() => {}}
        onSave={() => {}}
        onLoad={() => {}}
        onReset={() => {}}
        diagnostics={makeFindings()}
        onSelectModule={() => {}}
      />,
    );
    const cyclePill = screen.getByText('在环里 0');
    expect(cyclePill).toBeDisabled();
  });
});
