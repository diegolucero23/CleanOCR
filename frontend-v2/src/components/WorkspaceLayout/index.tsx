import type { LayoutRatio, PageData } from '@/types'
import { IndexPane } from '@/components/IndexPane'
import { ScanPane } from '@/components/ScanPane'
import { EditorPane } from '@/components/EditorPane'
import { PeekCard } from '@/components/PeekCard'

interface WorkspaceLayoutProps {
  layoutRatio: LayoutRatio
  pages: PageData[]
  currentPage: number
  currentPageData: PageData | null
  jobId: string | null
  isDirty: boolean
  progress?: number
  onPageSelect: (n: number) => void
  onNumPagesLoaded: (n: number) => void
  onEdit: (pageNumber: number, content: string) => void
  onReset: (pageNumber: number) => void
}

const GRID_TEMPLATES: Record<LayoutRatio, string> = {
  '50/50': '1fr 1fr',
  '60/40': '3fr 2fr',
  '40/60': '2fr 3fr',
  'INDEX': 'var(--rail-w) 1fr',
  'FOCUS': '1fr',
}

export function WorkspaceLayout({
  layoutRatio,
  pages,
  currentPage,
  currentPageData,
  jobId,
  isDirty,
  onPageSelect,
  onNumPagesLoaded,
  onEdit,
  onReset,
}: WorkspaceLayoutProps) {
  const isFocus = layoutRatio === 'FOCUS'
  const isIndex = layoutRatio === 'INDEX'

  return (
    <div
      style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: GRID_TEMPLATES[layoutRatio],
        transition: 'grid-template-columns 0.2s ease',
        overflow: 'hidden',
        minHeight: 0,
      }}
    >
      {/* Column 1: IndexPane (INDEX mode) or ScanPane (all others except FOCUS) */}
      {!isFocus && (
        isIndex ? (
          <IndexPane
            pages={pages}
            currentPage={currentPage}
            onPageSelect={onPageSelect}
          />
        ) : (
          <ScanPane
            jobId={jobId}
            pageNumber={currentPage}
            onNumPagesLoaded={onNumPagesLoaded}
          />
        )
      )}

      {/* Column 2: EditorPane (always) */}
      <EditorPane
        page={currentPageData}
        isDirty={isDirty}
        onEdit={onEdit}
        onReset={onReset}
      />

      {/* FOCUS mode: floating source peek */}
      {isFocus && (
        <PeekCard
          page={currentPageData}
          jobId={jobId}
          onClose={() => {}}
        />
      )}
    </div>
  )
}
