import React, { createContext, useContext, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

const TOAST_DURATION = 4000;

const iconMap: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={18} style={{ color: 'var(--success-primary)' }} />,
  error: <AlertCircle size={18} style={{ color: 'var(--error-primary)' }} />,
  warning: <AlertTriangle size={18} style={{ color: 'var(--warning-primary)' }} />,
  info: <Info size={18} style={{ color: 'var(--accent-primary)' }} />,
};

const bgMap: Record<ToastType, string> = {
  success: 'var(--success-subtle)',
  error: 'var(--error-subtle)',
  warning: 'var(--warning-subtle)',
  info: 'var(--accent-subtle)',
};

const borderMap: Record<ToastType, string> = {
  success: '2px solid var(--success-primary)',
  error: '2px solid var(--error-primary)',
  warning: '2px solid var(--warning-primary)',
  info: '2px solid var(--accent-primary)',
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, TOAST_DURATION);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-container">
        <AnimatePresence>
          {toasts.map(toast => (
            <motion.div
              key={toast.id}
              className="toast-item"
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 100, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              style={{
                background: bgMap[toast.type],
                borderLeft: borderMap[toast.type],
              }}
            >
              <div className="toast-content">
                {iconMap[toast.type]}
                <span className="toast-message">{toast.message}</span>
              </div>
              <button
                className="toast-close"
                onClick={() => removeToast(toast.id)}
                aria-label="Dismiss notification"
              >
                <X size={16} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextType {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

export default ToastContext;
