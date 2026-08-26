import { describe, expect, it } from 'vitest';
import { depthScore } from '../lib/depthScore';

describe('depthScore', () => {
  it('scores a small-interface / thick-implementation module as deep', () => {
    // 1 port at line 120 → ratio 120 ≥ 50 → deep
    expect(depthScore([{ line: 120 }])).toBe('deep');
  });

  it('scores a large-interface / thin-implementation module as shallow', () => {
    // 8 ports, last at line 40 → ratio 5 < 15 → shallow
    const ports = Array.from({ length: 8 }, (_, i) => ({ line: 10 + i * 4 }));
    expect(depthScore(ports)).toBe('shallow');
  });

  it('scores a middle-ground module as moderate', () => {
    // 3 ports, last at line 60 → ratio 20, 15 ≤ 20 < 50 → moderate
    expect(depthScore([{ line: 20 }, { line: 40 }, { line: 60 }])).toBe('moderate');
  });

  it('treats a zero-port module as shallow', () => {
    expect(depthScore([])).toBe('shallow');
  });
});
