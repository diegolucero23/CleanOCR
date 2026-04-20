import { useCallback, useEffect, useRef } from 'react'
import type { PageData } from '@/types'

const editKey = (jobId: string) => `cleanocr_v2_edits_${jobId}`

export function useEditorState(jobId: string | null) {
  const editsRef = useRef<Map<number, string>>(new Map())

  // Load persisted edits for this job on mount / jobId change
  useEffect(() => {
    if (!jobId) return
    try {
      const raw = localStorage.getItem(editKey(jobId))
      if (raw) {
        const parsed: Record<number, string> = JSON.parse(raw)
        editsRef.current = new Map(Object.entries(parsed).map(([k, v]) => [Number(k), v]))
      } else {
        editsRef.current = new Map()
      }
    } catch {
      editsRef.current = new Map()
    }
  }, [jobId])

  const flush = useCallback(() => {
    if (!jobId || editsRef.current.size === 0) return
    try {
      const obj = Object.fromEntries(editsRef.current)
      localStorage.setItem(editKey(jobId), JSON.stringify(obj))
    } catch (e) {
      console.error('[EditorState] flush failed:', e)
    }
  }, [jobId])

  const setEdit = useCallback(
    (pageNumber: number, content: string) => {
      editsRef.current.set(pageNumber, content)
      flush()
    },
    [flush],
  )

  const resetEdit = useCallback((pageNumber: number) => {
    editsRef.current.delete(pageNumber)
    flush()
  }, [flush])

  const getEdit = useCallback((pageNumber: number): string | undefined => {
    return editsRef.current.get(pageNumber)
  }, [])

  const isDirty = useCallback((pageNumber: number): boolean => {
    return editsRef.current.has(pageNumber)
  }, [])

  const exportAllEdits = useCallback((pages: PageData[]): PageData[] => {
    return pages.map((p) => ({
      ...p,
      editedContent: editsRef.current.get(p.pageNumber) ?? p.editedContent,
    }))
  }, [])

  // Flush on page unload
  useEffect(() => {
    window.addEventListener('beforeunload', flush)
    return () => window.removeEventListener('beforeunload', flush)
  }, [flush])

  return { setEdit, resetEdit, getEdit, isDirty, exportAllEdits, flush }
}
