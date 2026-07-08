import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { ToastMessage } from '@/types'

interface ToastContextValue {
  show: (text: string, variant?: ToastMessage['variant']) => void
}

const ToastContext = createContext<ToastContextValue>({ show: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const counterRef = useRef(0)

  const show = useCallback((text: string, variant: ToastMessage['variant'] = 'ok') => {
    const id = String(++counterRef.current)
    setToasts((prev) => [...prev.slice(-2), { id, text, variant }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 2800)
  }, [])

  const variantColor: Record<ToastMessage['variant'], string> = {
    ok: 'var(--ok)',
    warn: 'var(--warn)',
    err: 'var(--err)',
  }

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div
        style={{
          position: 'fixed',
          bottom: '24px',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          zIndex: 9999,
          pointerEvents: 'none',
        }}
      >
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.18 }}
              style={{
                background: 'var(--s3)',
                border: `1px solid ${variantColor[t.variant]}44`,
                borderLeft: `3px solid ${variantColor[t.variant]}`,
                borderRadius: 'var(--r-md)',
                padding: '9px 16px',
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                color: 'var(--t1)',
                boxShadow: 'var(--shad-over)',
                whiteSpace: 'nowrap',
              }}
            >
              {t.text}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
