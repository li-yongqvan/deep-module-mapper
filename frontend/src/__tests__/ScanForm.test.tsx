import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ScanForm from '../components/ScanForm';

describe('ScanForm', () => {
  it('calls onSubmit with the trimmed path when submitted', () => {
    const onSubmit = vi.fn();
    render(<ScanForm onSubmit={onSubmit} />);

    const input = screen.getByLabelText('代码目录路径');
    fireEvent.change(input, { target: { value: '  parser/tests/fixtures/sample_pkg  ' } });
    fireEvent.click(screen.getByRole('button', { name: '扫描' }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith('parser/tests/fixtures/sample_pkg');
  });

  it('disables the submit button when the path is empty (invariant #4)', () => {
    const onSubmit = vi.fn();
    render(<ScanForm onSubmit={onSubmit} />);

    const button = screen.getByRole('button', { name: '扫描' });
    expect(button).toBeDisabled();

    // Typing whitespace-only text still disables submission.
    fireEvent.change(screen.getByLabelText('代码目录路径'), { target: { value: '   ' } });
    expect(button).toBeDisabled();
  });

  it('does not submit when disabled', () => {
    const onSubmit = vi.fn();
    render(<ScanForm onSubmit={onSubmit} disabled />);

    fireEvent.change(screen.getByLabelText('代码目录路径'), {
      target: { value: 'some/path' },
    });
    fireEvent.click(screen.getByRole('button', { name: '扫描' }));

    expect(onSubmit).not.toHaveBeenCalled();
  });
});
