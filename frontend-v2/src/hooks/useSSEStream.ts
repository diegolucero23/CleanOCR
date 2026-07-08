import { useState, useEffect, useRef } from 'react'
import { subscribeToJobStatus } from '@/lib/api'
import type { JobResponse } from '@/types'

export function useSSEStream(jobId: string | null) {
  const [data, setData] = useState<JobResponse | null>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!jobId) return

    const cleanup = subscribeToJobStatus(
      jobId,
      (update) => setData(update),
      (err) => console.error('[SSE] stream error', err),
    )
    cleanupRef.current = cleanup

    return () => {
      cleanup()
      cleanupRef.current = null
    }
  }, [jobId])

  return data
}
