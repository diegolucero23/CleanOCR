import { useState } from 'react'
import { Search } from 'lucide-react'
import type { PageData } from '@/types'

interface IndexPaneProps {
  pages: PageData[]
  currentPage: number
  onPageSelect: (n: number) => void
}

export function IndexPane({ pages, currentPage, onPageSelect }: IndexPaneProps) {
  const [query, setQuery] = useState('')

  const filtered = query.trim()
    ? pages.filter(
        (p) =>
          String(p.pageNumber).includes(query) ||
          p.markdownContent.toLowerCase().includes(query.toLowerCase()) ||
          p.date?.toLowerCase().includes(query.toLowerCase()),
      )
    : pages

  // Group by volume/issue
  const groups = new Map<string, PageData[]>()
  for (const page of filtered) {
    const key = [page.volume && `Vol. ${page.volume}`, page.issue && `Iss. ${page.issue}`]
      .filter(Boolean)
      .join(' / ') || 'Ungrouped'
    const arr = groups.get(key) ?? []
    arr.push(page)
    groups.set(key, arr)
  }

  return (
    <div
      style={{
        width: 'var(--rail-w)',
        height: '100%',
        background: 'var(--s1)',
        borderRight: '1px solid var(--bord-d)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        flexShrink: 0,
      }}
    >
      {/* Search */}
      <div style={{ padding: '10px', borderBottom: '1px solid var(--bord-d)' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'var(--s3)',
            border: '1px solid var(--bord-d)',
            borderRadius: 'var(--r-sm)',
            padding: '5px 8px',
          }}
        >
          <Search size={12} color="var(--t4)" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages…"
            style={{
              background: 'none',
              border: 'none',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--t1)',
              outline: 'none',
              width: '100%',
            }}
          />
        </div>
      </div>

      {/* Page groups */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
        {groups.size === 0 ? (
          <div
            style={{
              padding: '20px 12px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--t4)',
              textAlign: 'center',
            }}
          >
            No pages
          </div>
        ) : (
          Array.from(groups.entries()).map(([groupKey, groupPages]) => (
            <div key={groupKey}>
              <div
                style={{
                  padding: '6px 12px 4px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '9px',
                  letterSpacing: '0.1em',
                  color: 'var(--t4)',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid var(--bord-d)',
                }}
              >
                {groupKey}
              </div>
              {groupPages.map((page) => {
                const isActive = page.pageNumber === currentPage
                const preview = page.markdownContent.replace(/\*\*[^*]+\*\*/g, '').trim().slice(0, 60)

                return (
                  <button
                    key={page.pageNumber}
                    onClick={() => onPageSelect(page.pageNumber)}
                    style={{
                      width: '100%',
                      padding: '7px 12px',
                      textAlign: 'left',
                      background: isActive ? 'var(--gold-tint)' : 'transparent',
                      border: 'none',
                      borderLeft: `2px solid ${isActive ? 'var(--gold)' : 'transparent'}`,
                      borderBottom: '1px solid var(--bord-d)',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '2px',
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) (e.currentTarget as HTMLElement).style.background = 'var(--s2)'
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '10px',
                          color: isActive ? 'var(--gold)' : 'var(--t2)',
                          letterSpacing: '0.05em',
                        }}
                      >
                        p. {page.pageNumber}
                      </span>
                      {page.date && (
                        <span
                          style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--t4)' }}
                        >
                          {page.date}
                        </span>
                      )}
                    </div>
                    {preview && (
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '10px',
                          color: 'var(--t3)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {preview}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
