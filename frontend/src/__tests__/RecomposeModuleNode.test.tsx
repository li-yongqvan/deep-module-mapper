import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ModuleNodeBody } from '../components/RecomposeModuleNode';
import type { RecomposeModuleData } from '../lib/recompose/derive';

function makeData(overrides: Partial<RecomposeModuleData> = {}): RecomposeModuleData {
  return {
    kind: 'recomposeModule',
    moduleId: 'mod:1',
    name: '目标模块',
    description: '聚合接口描述',
    atomIds: ['a', 'b'],
    implicit: false,
    memberNames: ['原子甲', '原子乙'],
    score: 'moderate',
    portCount: 3,
    onRename: vi.fn(),
    onSetDescription: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
}

describe('ModuleNodeBody', () => {
  it('shows the module name, interface line and score', () => {
    render(<ModuleNodeBody data={makeData()} />);
    expect(screen.getByText('目标模块')).toBeInTheDocument();
    expect(screen.getByText('接口')).toBeInTheDocument();
    expect(screen.getByText('聚合接口描述')).toBeInTheDocument();
    expect(screen.getByText('moderate')).toBeInTheDocument();
  });

  it('renames the module after double-click + Enter', () => {
    const data = makeData();
    render(<ModuleNodeBody data={data} />);
    fireEvent.doubleClick(screen.getByText('目标模块'));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '新名字' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(data.onRename).toHaveBeenCalledWith('新名字');
  });

  it('edits the interface description after double-click + Enter', () => {
    const data = makeData();
    render(<ModuleNodeBody data={data} />);
    fireEvent.doubleClick(screen.getByText('聚合接口描述'));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '新的接口描述' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(data.onSetDescription).toHaveBeenCalledWith('新的接口描述');
  });

  it('shows the delete button for explicit modules and fires onDelete', () => {
    const data = makeData();
    render(<ModuleNodeBody data={data} />);
    const del = screen.getByLabelText('删除模块');
    expect(del).toBeInTheDocument();
    fireEvent.click(del);
    expect(data.onDelete).toHaveBeenCalled();
  });

  it('hides the delete button for implicit single-atom modules', () => {
    const data = makeData({ implicit: true, atomIds: ['a'] });
    render(<ModuleNodeBody data={data} />);
    expect(screen.queryByLabelText('删除模块')).not.toBeInTheDocument();
  });

  it('ignores an empty rename commit', () => {
    const data = makeData();
    render(<ModuleNodeBody data={data} />);
    fireEvent.doubleClick(screen.getByText('目标模块'));
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(data.onRename).not.toHaveBeenCalled();
  });
});
