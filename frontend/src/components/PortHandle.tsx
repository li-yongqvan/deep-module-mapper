/**
 * Shared circular port handle (design doc §5.6 item 3 — "PortHandle: 封装小圆点
 * 把手样式"). One 10px accent dot with a 2px node-color border, used as the
 * module-level source/target handle on every node type (prototype §2.6).
 *
 * Code-review (PR #12): the identical handle style previously lived in
 * ModuleNode / ExternalNode / FeatureAtomNode; this is the single source.
 */
import { Handle, type HandleProps } from '@xyflow/react';
import type { CSSProperties } from 'react';

const handleStyle: CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: '50%',
  background: 'var(--accent, #38bdf8)',
  border: '2px solid var(--bg, #0f172a)',
};

export default function PortHandle({
  type,
  position,
}: Pick<HandleProps, 'type' | 'position'>) {
  return <Handle type={type} position={position} style={handleStyle} />;
}
