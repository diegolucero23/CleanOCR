// --- Job types (shared with backend) ---

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'cached'

export interface JobResponse {
  status: string
  job_id: string
  task_id?: string
  message?: string
  progress?: number
  markdown?: string
  upload_time?: number
  file_size?: number
  processing_time?: number
  complexity?: number
}

export interface PersistedJob {
  id: string
  uploaded_filename: string
  status: JobStatus
  progress: number
  timestamp: number
  markdown?: string
  resultMessage?: string
  upload_time?: number
  file_size?: number
  processing_time?: number
  complexity?: number
}

// --- v2-specific types ---

export interface PageData {
  pageNumber: number      // 1-based physical page number
  markdownContent: string
  volume?: string
  issue?: string
  date?: string
  isFlagged?: boolean
  editedContent?: string  // user's local edits
  confidence?: number     // future: per-page OCR confidence
}

export type LayoutRatio = '50/50' | '60/40' | '40/60' | 'INDEX' | 'FOCUS'

export interface AppState {
  mode: 'landing' | 'editor'
  job: PersistedJob | null
  pages: PageData[]
  currentPage: number
  layoutRatio: LayoutRatio
}

export interface UploadMetadata {
  title: string
  volume?: string
  issue?: string
  date?: string
}

export interface ToastMessage {
  id: string
  text: string
  variant: 'ok' | 'warn' | 'err'
}
