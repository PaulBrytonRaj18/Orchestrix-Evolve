import React from 'react';
import { motion } from 'framer-motion';
import { Check, Loader2, X, Circle } from 'lucide-react';
import type { AgentTrace } from '../types/api';

interface AgentTraceLogProps {
  trace: AgentTrace[];
}

function AgentTraceLog({ trace }: AgentTraceLogProps) {
  if (!trace || trace.length === 0) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: 'var(--space-4)',
          color: 'var(--text-tertiary)',
          fontSize: 'var(--text-sm)',
        }}
      >
        Waiting for agent activity...
      </div>
    );
  }

  const getStatusIcon = (status: string): React.ReactNode => {
    switch (status) {
      case 'done':
        return <Check size={14} style={{ color: 'var(--success-primary)' }} />;
      case 'running':
        return (
          <Loader2
            size={14}
            style={{ animation: 'spin 0.8s linear infinite', color: 'var(--accent-primary)' }}
          />
        );
      case 'error':
        return <X size={14} style={{ color: 'var(--error-primary)' }} />;
      default:
        return <Circle size={14} style={{ color: 'var(--text-tertiary)' }} />;
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'done':
        return 'var(--success-primary)';
      case 'running':
        return 'var(--accent-primary)';
      case 'error':
        return 'var(--error-primary)';
      default:
        return 'var(--text-tertiary)';
    }
  };

  return (
    <div className="trace-container">
      {trace.map((entry, index) => (
        <motion.div
          key={index}
          className="trace-item"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: index * 0.05 }}
        >
          <span
            className="trace-time"
            style={{
              color: 'var(--text-tertiary)',
              fontSize: 'var(--text-xs)',
              minWidth: '50px',
            }}
          >
            {entry.duration ? `${(entry.duration / 1000).toFixed(1)}s` : ''}
          </span>
          <span
            style={{
              color: getStatusColor(entry.status),
              minWidth: '20px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {getStatusIcon(entry.status)}
          </span>
          <span
            className="trace-agent"
            style={{ fontWeight: 'var(--font-medium)', color: 'var(--text-primary)' }}
          >
            {entry.agent}
          </span>
          <span className="trace-message" style={{ flex: 1 }}>
            {entry.status === 'done' && entry.result}
            {entry.status === 'running' && 'Processing...'}
            {entry.status === 'error' && entry.error}
            {entry.status === 'skipped' && entry.reason}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

export default AgentTraceLog;
