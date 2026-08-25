import { motion } from 'framer-motion';
import type { AgentStatus } from '../types';

export function AICore({ status, compact = false }: { status: AgentStatus; compact?: boolean }) {
  const active = status === 'executing' || status === 'thinking' || status === 'listening';
  return <motion.div className={`core-wrap ${compact ? 'core-compact' : ''} state-${status}`} animate={{ y: [0, -4, 0] }} transition={{ repeat: Infinity, duration: 4.6, ease: 'easeInOut' }} aria-label={`Agent ${status}`}>
    <motion.div className="core-halo" animate={{ rotate: active ? 360 : -12 }} transition={{ repeat: active ? Infinity : 0, duration: active ? 8 : 1.5, ease: 'linear' }} />
    <motion.div className="core-orbit orbit-inner" animate={{ rotate: status === 'executing' ? -360 : 0 }} transition={{ repeat: status === 'executing' ? Infinity : 0, duration: 4.2, ease: 'linear' }} />
    <motion.div className="core-glow" animate={{ scale: status === 'listening' ? [1, 1.18, 1] : [1, 1.06, 1] }} transition={{ repeat: Infinity, duration: status === 'idle' ? 4 : 1.7 }} />
    <div className="core-light"><span /><span /><span /></div>
    <div className="core-scan" />
    <i className="signal signal-a" /><i className="signal signal-b" /><i className="signal signal-c" />
  </motion.div>;
}
