import { useCallback, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { ZoomIn, ZoomOut, RotateCw, Loader2 } from 'lucide-react'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface ScanPaneProps {
  jobId: string | null
  pageNumber: number
  onNumPagesLoaded?: (n: number) => void
}

export function ScanPane({ jobId, pageNumber, onNumPagesLoaded }: ScanPaneProps) {
  const [scale, setScale] = useState(1.0)
  const [rotation, setRotation] = useState(0)

  const onDocumentLoadSuccess = useCallback(
    ({ numPages }: { numPages: number }) => {
      onNumPagesLoaded?.(numPages)
    },
    [onNumPagesLoaded],
  )

  const pdfUrl = jobId ? `/uploads/${jobId}.pdf` : null

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--s2)',
        borderRight: '1px solid var(--bord-d)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Scan area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'auto',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          padding: '20px',
        }}
      >
        {pdfUrl ? (
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '8px',
                  marginTop: '40px',
                  color: 'var(--t3)',
                }}
              >
                <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>Loading PDF…</span>
              </div>
            }
            error={
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--err)',
                  textAlign: 'center',
                  padding: '20px',
                }}
              >
                Failed to load PDF.
                <br />
                Is the backend running?
              </div>
            }
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              rotate={rotation}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className=""
            />
          </Document>
        ) : (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              marginTop: '60px',
              color: 'var(--t4)',
            }}
          >
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>No document loaded</span>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div
        style={{
          position: 'absolute',
          bottom: '16px',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          background: 'var(--s1)',
          border: '1px solid var(--bord-s)',
          borderRadius: '999px',
          padding: '5px 12px',
          boxShadow: 'var(--shad-card)',
        }}
      >
        <button
          onClick={() => setScale((s) => Math.max(0.4, parseFloat((s - 0.15).toFixed(2))))}
          className="icon-btn"
        >
          <ZoomOut size={13} color="var(--t2)" />
        </button>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            color: 'var(--t2)',
            minWidth: '40px',
            textAlign: 'center',
          }}
        >
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={() => setScale((s) => Math.min(3.0, parseFloat((s + 0.15).toFixed(2))))}
          className="icon-btn"
        >
          <ZoomIn size={13} color="var(--t2)" />
        </button>
        <div style={{ width: '1px', height: '14px', background: 'var(--bord-d)', margin: '0 4px' }} />
        <button onClick={() => setRotation((r) => (r + 90) % 360)} className="icon-btn">
          <RotateCw size={13} color="var(--t2)" />
        </button>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
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
