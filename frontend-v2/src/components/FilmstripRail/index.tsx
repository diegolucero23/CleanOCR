import { useEffect, useRef } from 'react'
import type { PageData } from '@/types'

interface FilmstripRailProps {
  pages: PageData[]
  currentPage: number
  totalPages: number
  progress?: number    // 0-100, shown while processing
  onPageSelect: (n: number) => void
}

function PlaceholderThumb({ n, isActive }: { n: number; isActive: boolean }) {
  return (
    <div
      style={{
        width: 52,
        height: 68,
        flexShrink: 0,
        background: 'var(--s3)',
        border: `1px solid ${isActive ? 'var(--gold)' : 'var(--bord-d)'}`,
        borderRadius: 'var(--r-sm)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 0.4,
      }}
    >
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--t4)' }}>{n}</span>
    </div>
  )
}

export function FilmstripRail({ pages, currentPage, totalPages, progress, onPageSelect }: FilmstripRailProps) {
  const railRef = useRef<HTMLDivElement>(null)
  const activeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [currentPage])

  const isProcessing = typeof progress === 'number' && progress < 100

  // Build display list: real pages + placeholders for unprocessed
  const pageMap = new Map(pages.map((p) => [p.pageNumber, p]))
  const displayCount = Math.max(totalPages, pages.length)

  return (
    <div
      style={{
        height: 'var(--filmstrip-h)',
        background: 'var(--s2)',
        borderBottom: '1px solid var(--bord-d)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        gap: '6px',
        overflowX: 'auto',
        overflowY: 'hidden',
        flexShrink: 0,
        position: 'relative',
      }}
      ref={railRef}
    >
      {isProcessing && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            height: '2px',
            width: `${progress}%`,
            background: 'var(--gold)',
            transition: 'width 0.4s ease',
            zIndex: 2,
          }}
        />
      )}

      {displayCount === 0 ? (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--t4)', margin: '0 auto' }}>
          No pages yet
        </span>
      ) : (
        Array.from({ length: displayCount }, (_, i) => {
          const n = i + 1
          const page = pageMap.get(n)
          const isActive = n === currentPage

          return (
            <div
              key={n}
              ref={isActive ? activeRef : undefined}
              onClick={() => page && onPageSelect(n)}
              style={{ cursor: page ? 'pointer' : 'default', position: 'relative' }}
            >
              {page ? (
                <div
                  style={{
                    width: 52,
                    height: 68,
                    flexShrink: 0,
                    background: 'var(--s3)',
                    border: `1.5px solid ${isActive ? 'var(--gold)' : page.isFlagged ? 'var(--err)' : 'var(--bord-d)'}`,
                    borderRadius: 'var(--r-sm)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '4px',
                    boxShadow: isActive ? '0 0 0 1px var(--gold-bord)' : 'none',
                    transition: 'border-color 0.15s',
                  }}
                >
                  {/* Mini text preview */}
                  <div
                    style={{
                      flex: 1,
                      width: '100%',
                      overflow: 'hidden',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '2px',
                      padding: '2px',
                    }}
                  >
                    {[0, 1, 2, 3].map((row) => (
                      <div
                        key={row}
                        style={{
                          height: '3px',
                          background: isActive ? 'var(--gold-tint)' : 'var(--s4)',
                          borderRadius: '1px',
                          width: row === 3 ? '60%' : '100%',
                          opacity: 0.6,
                        }}
                      />
                    ))}
                  </div>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '8px',
                      color: isActive ? 'var(--gold)' : 'var(--t4)',
                      letterSpacing: '0.05em',
                    }}
                  >
                    {n}
                  </span>
                </div>
              ) : (
                <PlaceholderThumb n={n} isActive={isActive} />
              )}

              {/* Flagged dot */}
              {page?.isFlagged && (
                <div
                  style={{
                    position: 'absolute',
                    top: '3px',
                    right: '3px',
                    width: '6px',
                    height: '6px',
                    background: 'var(--err)',
                    borderRadius: '50%',
                  }}
                />
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
