import { useCallback, useEffect, useMemo, useState } from 'react'
import { ToastProvider, useToast } from '@/components/ToastNotification'
import { TopBar } from '@/components/TopBar'
import { TitleBand } from '@/components/TitleBand'
import { FilmstripRail } from '@/components/FilmstripRail'
import { WorkspaceLayout } from '@/components/WorkspaceLayout'
import { UploadOverlay } from '@/components/UploadOverlay'
import { NavigationDrawer } from '@/components/NavigationDrawer'
import { TweaksPanel } from '@/components/TweaksPanel'
import { useJobPersistence } from '@/hooks/useJobPersistence'
import { useSSEStream } from '@/hooks/useSSEStream'
import { useEditorState } from '@/hooks/useEditorState'
import { parseMarkdownToPages } from '@/lib/parseMarkdown'
import type { JobResponse, LayoutRatio, PageData, PersistedJob } from '@/types'

function EditorApp() {
  const toast = useToast()
  const { history, addOrUpdateJob } = useJobPersistence()

  // --- UI state ---
  const [mode, setMode] = useState<'landing' | 'editor'>('landing')
  const [currentJob, setCurrentJob] = useState<PersistedJob | null>(null)
  const [pages, setPages] = useState<PageData[]>([])
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [layoutRatio, setLayoutRatio] = useState<LayoutRatio>('50/50')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [tweaksOpen, setTweaksOpen] = useState(false)
  const [lastEditedAt, setLastEditedAt] = useState<number | undefined>()

  // --- SSE stream (only active when job is queued/processing) ---
  const streamJobId =
    currentJob && (currentJob.status === 'queued' || currentJob.status === 'processing')
      ? currentJob.id
      : null
  const streamData = useSSEStream(streamJobId)

  // --- Editor state (per-page edits) ---
  const editorState = useEditorState(currentJob?.id ?? null)

  // --- Respond to SSE updates ---
  useEffect(() => {
    if (!streamData || !currentJob) return
    const updated: PersistedJob = {
      ...currentJob,
      status: streamData.status as PersistedJob['status'],
      progress: streamData.progress ?? currentJob.progress,
      resultMessage: streamData.message,
      markdown: streamData.markdown ?? currentJob.markdown,
      upload_time: streamData.upload_time ?? currentJob.upload_time,
      file_size: streamData.file_size ?? currentJob.file_size,
      processing_time: streamData.processing_time ?? currentJob.processing_time,
    }
    setCurrentJob(updated)
    addOrUpdateJob(updated)

    if (streamData.status === 'completed' && streamData.markdown) {
      const parsed = parseMarkdownToPages(streamData.markdown)
      setPages(parsed)
      setTotalPages(parsed.length)
      setCurrentPage(1)
      toast.show('OCR complete — document ready', 'ok')
    }
    if (streamData.status === 'failed') {
      toast.show(streamData.message ?? 'OCR failed', 'err')
    }
  }, [streamData]) // eslint-disable-line react-hooks/exhaustive-deps

  // --- Kick off editor mode for a job that's already completed ---
  const activateJob = useCallback(
    (job: PersistedJob) => {
      setCurrentJob(job)
      setMode('editor')
      if (job.markdown) {
        const parsed = parseMarkdownToPages(job.markdown)
        setPages(parsed)
        setTotalPages(parsed.length)
        setCurrentPage(1)
      } else {
        setPages([])
        setTotalPages(0)
      }
    },
    [],
  )

  // --- Handle new upload response ---
  const handleJobCreated = useCallback(
    (response: JobResponse, filename: string) => {
      const job: PersistedJob = {
        id: response.job_id,
        uploaded_filename: filename,
        status: response.status as PersistedJob['status'],
        progress: 0,
        timestamp: Date.now(),
      }
      addOrUpdateJob(job)
      activateJob(job)
    },
    [addOrUpdateJob, activateJob],
  )

  // --- Page navigation ---
  const goToPage = useCallback(
    (n: number) => setCurrentPage(Math.max(1, Math.min(totalPages || 1, n))),
    [totalPages],
  )

  // --- Current page data (with local edits merged in) ---
  const currentPageData = useMemo<PageData | null>(() => {
    const page = pages.find((p) => p.pageNumber === currentPage) ?? null
    if (!page) return null
    const edit = editorState.getEdit(page.pageNumber)
    return edit !== undefined ? { ...page, editedContent: edit } : page
  }, [pages, currentPage, editorState])

  // --- Editor callbacks ---
  const handleEdit = useCallback(
    (pageNumber: number, content: string) => {
      editorState.setEdit(pageNumber, content)
      setLastEditedAt(Date.now())
    },
    [editorState],
  )

  const handleReset = useCallback(
    (pageNumber: number) => {
      editorState.resetEdit(pageNumber)
      setLastEditedAt(Date.now())
      toast.show('Reset to original', 'ok')
    },
    [editorState, toast],
  )

  // --- Export helpers ---
  const buildExportMarkdown = useCallback(() => {
    if (!currentJob) return ''
    if (pages.length === 0) return currentJob.markdown ?? ''
    return editorState
      .exportAllEdits(pages)
      .map((p) => (p.editedContent ?? p.markdownContent))
      .join('\n----------\n')
  }, [currentJob, pages, editorState])

  const handleExportMd = useCallback(() => {
    const md = buildExportMarkdown()
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentJob?.uploaded_filename ?? 'document'}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.show('Exported markdown', 'ok')
  }, [buildExportMarkdown, currentJob, toast])

  const handleExportJson = useCallback(() => {
    const exported = editorState.exportAllEdits(pages)
    const data = {
      job_id: currentJob?.id,
      filename: currentJob?.uploaded_filename,
      exported_at: new Date().toISOString(),
      pages: exported.map((p) => ({
        pageNumber: p.pageNumber,
        volume: p.volume,
        issue: p.issue,
        date: p.date,
        markdownContent: p.editedContent ?? p.markdownContent,
        originalContent: p.editedContent ? p.markdownContent : undefined,
      })),
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentJob?.uploaded_filename ?? 'document'}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.show('Exported JSON', 'ok')
  }, [currentJob, pages, editorState, toast])

  const handleExportClipboard = useCallback(() => {
    const md = buildExportMarkdown()
    navigator.clipboard.writeText(md).then(() => toast.show('Copied to clipboard', 'ok'))
  }, [buildExportMarkdown, toast])

  // --- Keyboard shortcuts ---
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'Escape' && layoutRatio === 'FOCUS') setLayoutRatio('50/50')
      if (e.key === '1') setLayoutRatio('50/50')
      if (e.key === '2') setLayoutRatio('60/40')
      if (e.key === '3') setLayoutRatio('40/60')
      if (e.key === '4') setLayoutRatio('INDEX')
      if (e.key === 'f' || e.key === 'F') setLayoutRatio('FOCUS')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [layoutRatio])

  // --- Landing ---
  if (mode === 'landing') {
    return <UploadOverlay onJobCreated={handleJobCreated} />
  }

  const progress = currentJob?.progress

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <TopBar
        layoutRatio={layoutRatio}
        onLayoutChange={setLayoutRatio}
        onMenuOpen={() => setDrawerOpen(true)}
        onTweaksOpen={() => setTweaksOpen(true)}
        onExportMd={handleExportMd}
        onExportJson={handleExportJson}
        onExportClipboard={handleExportClipboard}
      />

      <TitleBand
        title={currentJob?.uploaded_filename?.replace(/\.pdf$/i, '') ?? 'Untitled'}
        volume={currentPageData?.volume}
        issue={currentPageData?.issue}
        currentPage={currentPage}
        totalPages={totalPages}
        lastEditedAt={lastEditedAt}
        onPrev={() => goToPage(currentPage - 1)}
        onNext={() => goToPage(currentPage + 1)}
      />

      <FilmstripRail
        pages={pages}
        currentPage={currentPage}
        totalPages={totalPages}
        progress={progress}
        onPageSelect={goToPage}
      />

      <WorkspaceLayout
        layoutRatio={layoutRatio}
        pages={pages}
        currentPage={currentPage}
        currentPageData={currentPageData}
        jobId={currentJob?.id ?? null}
        isDirty={currentPageData ? editorState.isDirty(currentPageData.pageNumber) : false}
        progress={progress}
        onPageSelect={goToPage}
        onNumPagesLoaded={setTotalPages}
        onEdit={handleEdit}
        onReset={handleReset}
      />

      <NavigationDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        jobs={history}
        currentJobId={currentJob?.id ?? null}
        onJobSelect={activateJob}
        onNewUpload={() => setMode('landing')}
      />

      <TweaksPanel isOpen={tweaksOpen} onClose={() => setTweaksOpen(false)} />
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <EditorApp />
    </ToastProvider>
  )
}
