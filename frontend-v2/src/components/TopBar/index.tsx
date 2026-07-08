import { useRef, useState } from 'react'
import { Menu, Search, Download, ChevronDown, Settings } from 'lucide-react'
import type { LayoutRatio } from '@/types'

const RATIOS: { label: string; value: LayoutRatio }[] = [
  { label: '50·50', value: '50/50' },
  { label: '60·40', value: '60/40' },
  { label: '40·60', value: '40/60' },
  { label: 'INDEX', value: 'INDEX' },
  { label: 'FOCUS', value: 'FOCUS' },
]

interface TopBarProps {
  layoutRatio: LayoutRatio
  onLayoutChange: (r: LayoutRatio) => void
  onMenuOpen: () => void
  onTweaksOpen: () => void
  onExportMd: () => void
  onExportJson: () => void
  onExportClipboard: () => void
}

export function TopBar({
  layoutRatio,
  onLayoutChange,
  onMenuOpen,
  onTweaksOpen,
  onExportMd,
  onExportJson,
  onExportClipboard,
}: TopBarProps) {
  const [exportOpen, setExportOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const exportRef = useRef<HTMLDivElement>(null)

  return (
    <header
      style={{
        height: 'var(--topbar-h)',
        background: 'var(--s1)',
        borderBottom: '1px solid var(--bord-d)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        gap: '12px',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        flexShrink: 0,
      }}
    >
      {/* Brand + Menu */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: '140px' }}>
        <button onClick={onMenuOpen} className="icon-btn" aria-label="Menu">
          <Menu size={16} color="var(--t3)" />
        </button>
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '18px',
            letterSpacing: '0.08em',
            color: 'var(--t1)',
          }}
        >
          CLEAN<span style={{ color: 'var(--gold)' }}>·</span>OCR
        </span>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--gold-dim)',
            background: 'var(--gold-tint)',
            border: '1px solid var(--gold-bord)',
            borderRadius: 'var(--r-sm)',
            padding: '1px 5px',
            letterSpacing: '0.1em',
          }}
        >
          V2
        </span>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Layout segmented control */}
      <div
        style={{
          display: 'flex',
          background: 'var(--s2)',
          border: '1px solid var(--bord-d)',
          borderRadius: 'var(--r-md)',
          overflow: 'hidden',
        }}
      >
        {RATIOS.map(({ label, value }) => (
          <button
            key={value}
            onClick={() => onLayoutChange(value)}
            style={{
              padding: '5px 10px',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              letterSpacing: '0.06em',
              background: layoutRatio === value ? 'var(--s4)' : 'transparent',
              color: layoutRatio === value ? 'var(--gold)' : 'var(--t3)',
              border: 'none',
              cursor: 'pointer',
              borderRight: '1px solid var(--bord-d)',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Right icons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {searchOpen && (
          <input
            autoFocus
            onBlur={() => setSearchOpen(false)}
            placeholder="Search pages…"
            style={{
              background: 'var(--s3)',
              border: '1px solid var(--bord-s)',
              borderRadius: 'var(--r-sm)',
              padding: '4px 8px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--t1)',
              width: '180px',
              outline: 'none',
            }}
          />
        )}
        <button className="icon-btn" onClick={() => setSearchOpen((v) => !v)} aria-label="Search">
          <Search size={15} color="var(--t3)" />
        </button>

        {/* Export dropdown */}
        <div ref={exportRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setExportOpen((v) => !v)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 10px',
              background: 'var(--gold-tint)',
              border: '1px solid var(--gold-bord)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--gold)',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              letterSpacing: '0.08em',
              cursor: 'pointer',
            }}
          >
            <Download size={12} />
            EXPORT
            <ChevronDown size={11} />
          </button>

          {exportOpen && (
            <>
              <div
                style={{
                  position: 'fixed',
                  inset: 0,
                  zIndex: 59,
                }}
                onClick={() => setExportOpen(false)}
              />
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  right: 0,
                  background: 'var(--s2)',
                  border: '1px solid var(--bord-s)',
                  borderRadius: 'var(--r-md)',
                  boxShadow: 'var(--shad-over)',
                  minWidth: '180px',
                  zIndex: 60,
                  overflow: 'hidden',
                }}
              >
                {[
                  { label: 'Markdown (.md)', action: () => { onExportMd(); setExportOpen(false) } },
                  { label: 'JSON (.json)', action: () => { onExportJson(); setExportOpen(false) } },
                  { label: 'Copy to clipboard', action: () => { onExportClipboard(); setExportOpen(false) } },
                ].map(({ label, action }) => (
                  <button
                    key={label}
                    onClick={action}
                    style={{
                      width: '100%',
                      padding: '9px 14px',
                      textAlign: 'left',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: '1px solid var(--bord-d)',
                      color: 'var(--t2)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '11px',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--s3)' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <button className="icon-btn" onClick={onTweaksOpen} aria-label="Settings">
          <Settings size={15} color="var(--t3)" />
        </button>
      </div>
    </header>
  )
}
