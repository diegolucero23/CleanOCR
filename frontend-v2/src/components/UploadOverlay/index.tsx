import { useCallback, useRef, useState } from 'react'
import { Upload, X } from 'lucide-react'
import { uploadFile } from '@/lib/api'
import type { JobResponse, UploadMetadata } from '@/types'

interface UploadOverlayProps {
  onJobCreated: (response: JobResponse, filename: string) => void
}

export function UploadOverlay({ onJobCreated }: UploadOverlayProps) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [metadata, setMetadata] = useState<UploadMetadata>({ title: '' })
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.type === 'application/pdf') {
      setFile(dropped)
      setMetadata((m) => ({ ...m, title: dropped.name.replace(/\.pdf$/i, '') }))
    } else {
      setError('Only PDF files are supported.')
    }
  }, [])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0]
    if (picked) {
      setFile(picked)
      setMetadata((m) => ({ ...m, title: picked.name.replace(/\.pdf$/i, '') }))
    }
  }

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const response = await uploadFile(file, metadata)
      onJobCreated(response, file.name)
    } catch (e) {
      setError('Upload failed. Is the backend running?')
      console.error(e)
    } finally {
      setUploading(false)
    }
  }

  const field = (label: string, key: keyof UploadMetadata, placeholder: string) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <label
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '9px',
          letterSpacing: '0.1em',
          color: 'var(--t4)',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </label>
      <input
        value={metadata[key] ?? ''}
        onChange={(e) => setMetadata((m) => ({ ...m, [key]: e.target.value }))}
        placeholder={placeholder}
        style={{
          background: 'var(--s3)',
          border: '1px solid var(--bord-d)',
          borderRadius: 'var(--r-sm)',
          padding: '7px 10px',
          fontFamily: 'var(--font-mono)',
          fontSize: '12px',
          color: 'var(--t1)',
          outline: 'none',
        }}
        onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--gold-bord)' }}
        onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--bord-d)' }}
      />
    </div>
  )

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--canvas)',
        zIndex: 10,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '480px',
          padding: '0 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
        }}
      >
        {/* Wordmark */}
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '3rem',
              letterSpacing: '0.1em',
              color: 'var(--t1)',
            }}
          >
            CLEAN<span style={{ color: 'var(--gold)' }}>·</span>OCR
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--t4)',
              letterSpacing: '0.12em',
              marginTop: '4px',
            }}
          >
            PDF → CLEAN MARKDOWN
          </div>
        </div>

        {/* Drop zone or file selected */}
        {!file ? (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            style={{
              border: `2px dashed ${dragging ? 'var(--gold)' : 'var(--bord-m)'}`,
              borderRadius: 'var(--r-lg)',
              padding: '40px 24px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '10px',
              cursor: 'pointer',
              background: dragging ? 'var(--gold-tint)' : 'var(--s1)',
              transition: 'all 0.15s',
            }}
          >
            <Upload size={28} color={dragging ? 'var(--gold)' : 'var(--t4)'} />
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--t2)' }}>
              Drop a PDF here
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--t4)' }}>
              or click to browse
            </span>
            <input ref={inputRef} type="file" accept=".pdf" style={{ display: 'none' }} onChange={handleFileInput} />
          </div>
        ) : (
          <div
            style={{
              background: 'var(--s2)',
              border: '1px solid var(--bord-s)',
              borderRadius: 'var(--r-lg)',
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            {/* File header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--gold)' }}>
                {file.name}
              </span>
              <button
                onClick={() => setFile(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
              >
                <X size={13} color="var(--t3)" />
              </button>
            </div>

            {/* Metadata fields */}
            {field('Title', 'title', 'Document title')}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
              {field('Volume', 'volume', '1')}
              {field('Issue', 'issue', '1')}
              {field('Date', 'date', '1863')}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--err)',
              textAlign: 'center',
            }}
          >
            {error}
          </div>
        )}

        {/* Submit */}
        {file && (
          <button
            onClick={handleSubmit}
            disabled={uploading || !metadata.title.trim()}
            style={{
              padding: '12px',
              background: uploading || !metadata.title.trim() ? 'var(--s3)' : 'var(--gold)',
              border: 'none',
              borderRadius: 'var(--r-md)',
              color: uploading || !metadata.title.trim() ? 'var(--t4)' : 'var(--canvas)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              letterSpacing: '0.1em',
              cursor: uploading || !metadata.title.trim() ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {uploading ? 'UPLOADING…' : 'START OCR →'}
          </button>
        )}
      </div>
    </div>
  )
}
