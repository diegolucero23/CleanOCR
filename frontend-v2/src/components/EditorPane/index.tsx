import { useCallback, useEffect, useRef, useState } from 'react'
import { Bold, Italic, Quote, List, Code, RotateCcw } from 'lucide-react'
import { wordCount } from '@/lib/utils'
import type { PageData } from '@/types'

interface EditorPaneProps {
  page: PageData | null
  isDirty: boolean
  onEdit: (pageNumber: number, content: string) => void
  onReset: (pageNumber: number) => void
}

export function EditorPane({ page, isDirty, onEdit, onReset }: EditorPaneProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [localContent, setLocalContent] = useState('')

  // Sync content when page changes
  useEffect(() => {
    if (!page) return
    setLocalContent(page.editedContent ?? page.markdownContent)
  }, [page?.pageNumber]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value
      setLocalContent(val)
      if (!page) return
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        onEdit(page.pageNumber, val)
      }, 300)
    },
    [page, onEdit],
  )

  const wrapSelection = useCallback(
    (before: string, after = before) => {
      const ta = textareaRef.current
      if (!ta) return
      const { selectionStart: s, selectionEnd: e, value } = ta
      const wrapped = value.slice(0, s) + before + value.slice(s, e) + after + value.slice(e)
      setLocalContent(wrapped)
      if (page) onEdit(page.pageNumber, wrapped)
      setTimeout(() => {
        ta.focus()
        ta.setSelectionRange(s + before.length, e + before.length)
      }, 0)
    },
    [page, onEdit],
  )

  const chars = localContent.length
  const words = wordCount(localContent)

  if (!page) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--canvas)',
          color: 'var(--t4)',
          fontFamily: 'var(--font-mono)',
          fontSize: '12px',
        }}
      >
        No page selected
      </div>
    )
  }

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--canvas)',
        overflow: 'hidden',
      }}
    >
      {/* Formatting toolbar */}
      <div
        style={{
          height: '36px',
          display: 'flex',
          alignItems: 'center',
          gap: '2px',
          padding: '0 10px',
          borderBottom: '1px solid var(--bord-d)',
          background: 'var(--s1)',
          flexShrink: 0,
        }}
      >
        {[
          { icon: <Bold size={13} />, title: 'Bold', wrap: '**' },
          { icon: <Italic size={13} />, title: 'Italic', wrap: '_' },
          { icon: <Quote size={13} />, title: 'Blockquote', before: '\n> ', after: '' },
          { icon: <List size={13} />, title: 'List item', before: '\n- ', after: '' },
          { icon: <Code size={13} />, title: 'Inline code', wrap: '`' },
        ].map(({ icon, title, wrap, before, after }) => (
          <button
            key={title}
            title={title}
            onClick={() =>
              wrap ? wrapSelection(wrap) : wrapSelection(before ?? '', after ?? '')
            }
            className="icon-btn"
          >
            <span style={{ color: 'var(--t3)' }}>{icon}</span>
          </button>
        ))}

        <div style={{ flex: 1 }} />

        {isDirty && (
          <button
            title="Reset to original"
            onClick={() => onReset(page.pageNumber)}
            className="icon-btn"
            style={{ opacity: 0.7 }}
          >
            <RotateCcw size={12} color="var(--warn)" />
          </button>
        )}

        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--t4)',
            letterSpacing: '0.06em',
          }}
        >
          {isDirty ? '● ' : ''}p.{page.pageNumber}
        </span>
      </div>

      {/* Editor body */}
      <textarea
        ref={textareaRef}
        value={localContent}
        onChange={handleChange}
        spellCheck={false}
        style={{
          flex: 1,
          background: 'var(--canvas)',
          color: 'var(--t1)',
          fontFamily: 'var(--font-mono)',
          fontSize: '13px',
          lineHeight: '1.7',
          padding: '24px 32px',
          border: 'none',
          outline: 'none',
          resize: 'none',
          overflowY: 'auto',
        }}
      />

      {/* Footer bar */}
      <div
        style={{
          height: '28px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '0 14px',
          borderTop: '1px solid var(--bord-d)',
          background: 'var(--s1)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--t4)' }}>
          {chars.toLocaleString()} chars · {words.toLocaleString()} words
        </span>
        <div style={{ flex: 1 }} />
        {page.confidence !== undefined && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              color: page.confidence > 0.95 ? 'var(--ok)' : page.confidence > 0.85 ? 'var(--warn)' : 'var(--err)',
              background: 'var(--s2)',
              border: '1px solid var(--bord-d)',
              borderRadius: 'var(--r-sm)',
              padding: '1px 6px',
            }}
          >
            {Math.round(page.confidence * 100)}% conf.
          </span>
        )}
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--t4)' }}>
          MD · UTF-8
        </span>
      </div>

      <style>{`
        .icon-btn {
          display: flex; align-items: center; justify-content: center;
          width: 28px; height: 28px;
          background: transparent; border: none; cursor: pointer;
          border-radius: var(--r-sm);
          transition: background 0.12s;
        }
        .icon-btn:hover { background: var(--s3); }
      `}</style>
    </div>
  )
}
