import axios from 'axios'
import type { JobResponse, UploadMetadata } from '@/types'

const API = axios.create({
  baseURL: '/api',
  headers: { Accept: 'application/json' },
})

export const uploadFile = async (
  file: File,
  metadata?: UploadMetadata,
  skipMetadata = false,
): Promise<JobResponse> => {
  const formData = new FormData()
  formData.append('file', file)

  if (skipMetadata) {
    formData.append('skip_metadata', 'true')
  } else if (metadata) {
    formData.append('title', metadata.title)
    if (metadata.volume) formData.append('volume', metadata.volume)
    if (metadata.issue) formData.append('issue', metadata.issue)
    if (metadata.date) formData.append('date', metadata.date)
  }

  const response = await API.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const pollJobStatus = async (jobId: string): Promise<JobResponse> => {
  const response = await API.get<JobResponse>(`/status/${jobId}`)
  return response.data
}

export const subscribeToJobStatus = (
  jobId: string,
  onUpdate: (data: JobResponse) => void,
  onError?: (err: Event) => void,
): (() => void) => {
  const source = new EventSource(`/api/stream/${jobId}`)

  source.onmessage = (event) => {
    try {
      const data: JobResponse = JSON.parse(event.data as string)
      onUpdate(data)
      if (data.status === 'completed' || data.status === 'failed') {
        source.close()
      }
    } catch (e) {
      console.error(`SSE parse error for ${jobId}`, e)
    }
  }

  source.onerror = (err) => {
    onError?.(err)
    source.close()
  }

  return () => source.close()
}
