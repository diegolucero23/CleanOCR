import { ChevronLeft, ChevronRight } from 'lucide-react'

interface TitleBandProps {
  title: string
  volume?: string
  issue?: string
  currentPage: number
  totalPages: number
  lastEditedAt?: number
  onPrev: () => void
  onNext: () => void
}

export function TitleBand({
  title,
  volume,
  issue,
  currentPage,
  totalPages,
  lastEditedAt,
  onPrev,
  onNext,
}: TitleBandProps) {
  const lastEdit = lastEditedAt
    ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(
        new Date(lastEditedAt),
      )
    : null

  return (
    <div
      style={{
        height: 'var(--titleband-h)',
        background: 'var(--s1)',
        borderBottom: '1px solid var(--bord-d)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '16px',
        flexShrink: 0,
      }}
    >
      {/* Title + metadata */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'baseline', gap: '10px' }}>
        <span
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '15px',
            color: 'var(--t1)',
            fontStyle: 'italic',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title || 'Untitled Document'}
        </span>
        {(volume || issue) && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              color: 'var(--t3)',
              letterSpacing: '0.08em',
              whiteSpace: 'nowrap',
            }}
          >
            {[volume && `Vol. ${volume}`, issue && `Iss. ${issue}`].filter(Boolean).join(' · ')}
          </span>
        )}
      </div>

      {/* Page counter + nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
        <button
          onClick={onPrev}
          disabled={currentPage <= 1}
          style={{
            background: 'none',
            border: 'none',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            opacity: currentPage <= 1 ? 0.3 : 1,
            display: 'flex',
            padding: '4px',
          }}
        >
          <ChevronLeft size={14} color="var(--t2)" />
        </button>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--t2)',
            minWidth: '80px',
            textAlign: 'center',
          }}
        >
          {totalPages === 0 ? '—' : `${currentPage} / ${totalPages}`}
        </span>
        <button
          onClick={onNext}
          disabled={currentPage >= totalPages}
          style={{
            background: 'none',
            border: 'none',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            opacity: currentPage >= totalPages ? 0.3 : 1,
            display: 'flex',
            padding: '4px',
          }}
        >
          <ChevronRight size={14} color="var(--t2)" />
        </button>
      </div>

      {/* Last edited */}
      {lastEdit && (
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            color: 'var(--t4)',
            flexShrink: 0,
          }}
        >
          edited {lastEdit}
        </span>
      )}
    </div>
  )
}
