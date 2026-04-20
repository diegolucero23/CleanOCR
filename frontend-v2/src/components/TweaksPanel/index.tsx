import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useState } from 'react'

interface TweaksPanelProps {
  isOpen: boolean
  onClose: () => void
}

interface Toggle {
  label: string
  description: string
  key: string
  cssVar?: string
  cssValue?: string
  defaultOff?: string
}

const TWEAKS: Toggle[] = [
  {
    label: 'Serif headings',
    description: 'Use DM Serif Display for H1 in the editor',
    key: 'serif-h1',
  },
  {
    label: 'Gold dim mode',
    description: 'Reduce gold accent intensity',
    key: 'gold-dim',
    cssVar: '--gold',
    cssValue: '#a08754',
    defaultOff: '#c8a96e',
  },
  {
    label: 'Compact layout',
    description: 'Reduce filmstrip and titleband height',
    key: 'compact',
  },
]

export function TweaksPanel({ isOpen, onClose }: TweaksPanelProps) {
  const [states, setStates] = useState<Record<string, boolean>>({})

  const toggle = (key: string, tweak: Toggle) => {
    const next = !states[key]
    setStates((prev) => ({ ...prev, [key]: next }))

    if (tweak.cssVar) {
      document.documentElement.style.setProperty(
        tweak.cssVar,
        next ? (tweak.cssValue ?? '') : (tweak.defaultOff ?? ''),
      )
    }

    if (key === 'compact') {
      document.documentElement.style.setProperty('--filmstrip-h', next ? '72px' : '96px')
      document.documentElement.style.setProperty('--titleband-h', next ? '40px' : '52px')
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            style={{ position: 'fixed', inset: 0, zIndex: 60 }}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.2, ease: 'easeOut' }}
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: '260px',
              background: 'var(--s1)',
              borderLeft: '1px solid var(--bord-s)',
              display: 'flex',
              flexDirection: 'column',
              zIndex: 61,
              boxShadow: 'var(--shad-over)',
            }}
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 16px',
                borderBottom: '1px solid var(--bord-d)',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.1em',
                  color: 'var(--t2)',
                  textTransform: 'uppercase',
                }}
              >
                Tweaks
              </span>
              <button
                onClick={onClose}
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
              >
                <X size={15} color="var(--t3)" />
              </button>
            </div>

            {/* Toggles */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
              {TWEAKS.map((tweak) => {
                const on = !!states[tweak.key]
                return (
                  <div
                    key={tweak.key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 16px',
                      borderBottom: '1px solid var(--bord-d)',
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '11px',
                          color: 'var(--t1)',
                        }}
                      >
                        {tweak.label}
                      </div>
                      <div
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '9px',
                          color: 'var(--t4)',
                          marginTop: '2px',
                        }}
                      >
                        {tweak.description}
                      </div>
                    </div>
                    {/* Toggle switch */}
                    <button
                      onClick={() => toggle(tweak.key, tweak)}
                      style={{
                        width: '32px',
                        height: '18px',
                        borderRadius: '9px',
                        background: on ? 'var(--gold)' : 'var(--s4)',
                        border: 'none',
                        cursor: 'pointer',
                        position: 'relative',
                        transition: 'background 0.15s',
                        flexShrink: 0,
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          top: '2px',
                          left: on ? '16px' : '2px',
                          width: '14px',
                          height: '14px',
                          borderRadius: '50%',
                          background: 'var(--t1)',
                          transition: 'left 0.15s',
                        }}
                      />
                    </button>
                  </div>
                )
              })}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
