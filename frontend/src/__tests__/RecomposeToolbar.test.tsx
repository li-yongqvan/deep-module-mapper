import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import RecomposeToolbar from '../components/RecomposeToolbar';

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
});
