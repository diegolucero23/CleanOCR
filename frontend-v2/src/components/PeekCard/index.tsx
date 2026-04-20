import { useState } from 'react'
import { X } from 'lucide-react'
import type { PageData } from '@/types'

interface PeekCardProps {
  page: PageData | null
  jobId: string | null
  onClose: () => void
}

export function PeekCard({ page, jobId: _jobId, onClose }: PeekCardProps) {
  const [expanded, setExpanded] = useState(false)

  if (!page) return null

  return (
    <div
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        width: expanded ? '320px' : '200px',
        background: 'var(--s2)',
        border: '1px solid var(--bord-s)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--shad-over)',
        overflow: 'hidden',
        transition: 'width 0.2s ease',
        zIndex: 40,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          borderBottom: '1px solid var(--bord-d)',
        }}
      >
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--gold)', letterSpacing: '0.1em' }}>
          SOURCE · p.{page.pageNumber}
        </span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', padding: '2px' }}
        >
          <X size={11} color="var(--t4)" />
        </button>
      </div>

      {/* Content preview */}
      <div
        style={{
          padding: '8px 10px',
          maxHeight: expanded ? '200px' : '80px',
          overflowY: 'hidden',
          transition: 'max-height 0.2s ease',
        }}
      >
        <pre
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--t3)',
            lineHeight: '1.5',
            whiteSpace: 'pre-wrap',
            margin: 0,
          }}
        >
          {page.markdownContent.replace(/\*\*[^*]+\*\*/g, '').trim().slice(0, expanded ? 600 : 150)}
        </pre>
      </div>
    </div>
  )
}
