import { AnimatePresence, motion } from 'framer-motion'
import { Clock, FileText, X } from 'lucide-react'
import type { PersistedJob } from '@/types'

interface NavigationDrawerProps {
  isOpen: boolean
  onClose: () => void
  jobs: PersistedJob[]
  currentJobId: string | null
  onJobSelect: (job: PersistedJob) => void
  onNewUpload: () => void
}

const STATUS_COLOR: Record<string, string> = {
  completed: 'var(--ok)',
  processing: 'var(--warn)',
  queued: 'var(--warn)',
  failed: 'var(--err)',
  cached: 'var(--ok)',
}

export function NavigationDrawer({
  isOpen,
  onClose,
  jobs,
  currentJobId,
  onJobSelect,
  onNewUpload,
}: NavigationDrawerProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              zIndex: 60,
            }}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              bottom: 0,
              width: '300px',
              background: 'var(--s1)',
              borderRight: '1px solid var(--bord-s)',
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
                  fontFamily: 'var(--font-display)',
                  fontSize: '16px',
                  letterSpacing: '0.08em',
                  color: 'var(--t1)',
                }}
              >
                CLEAN<span style={{ color: 'var(--gold)' }}>·</span>OCR
              </span>
              <button onClick={onClose} className="icon-btn">
                <X size={15} color="var(--t3)" />
              </button>
            </div>

            {/* New upload button */}
            <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--bord-d)' }}>
              <button
                onClick={() => { onNewUpload(); onClose() }}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: 'var(--gold-tint)',
                  border: '1px solid var(--gold-bord)',
                  borderRadius: 'var(--r-md)',
                  color: 'var(--gold)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.08em',
                  cursor: 'pointer',
                }}
              >
                + NEW UPLOAD
              </button>
            </div>

            {/* Job history */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              <div
                style={{
                  padding: '8px 12px 4px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '9px',
                  letterSpacing: '0.1em',
                  color: 'var(--t4)',
                  textTransform: 'uppercase',
                }}
              >
                Recent Documents
              </div>

              {jobs.length === 0 ? (
                <div
                  style={{
                    padding: '20px 12px',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '11px',
                    color: 'var(--t4)',
                    textAlign: 'center',
                  }}
                >
                  No documents yet
                </div>
              ) : (
                jobs.map((job) => {
                  const isActive = job.id === currentJobId
                  return (
                    <button
                      key={job.id}
                      onClick={() => { onJobSelect(job); onClose() }}
                      style={{
                        width: '100%',
                        padding: '9px 12px',
                        textAlign: 'left',
                        background: isActive ? 'var(--gold-tint)' : 'transparent',
                        border: 'none',
                        borderLeft: `2px solid ${isActive ? 'var(--gold)' : 'transparent'}`,
                        borderBottom: '1px solid var(--bord-d)',
                        cursor: 'pointer',
                        display: 'flex',
                        gap: '10px',
                        alignItems: 'flex-start',
                      }}
                      onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'var(--s2)' }}
                      onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      <FileText size={13} color={isActive ? 'var(--gold)' : 'var(--t4)'} style={{ marginTop: 1, flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '11px',
                            color: isActive ? 'var(--t1)' : 'var(--t2)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {job.uploaded_filename}
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '3px' }}>
                          <div
                            style={{
                              width: '6px',
                              height: '6px',
                              borderRadius: '50%',
                              background: STATUS_COLOR[job.status] ?? 'var(--t4)',
                              flexShrink: 0,
                            }}
                          />
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--t4)' }}>
                            {job.status}
                          </span>
                          <Clock size={9} color="var(--t4)" />
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--t4)' }}>
                            {new Date(job.timestamp).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </button>
                  )
                })
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
