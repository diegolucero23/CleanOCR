import { useState, useCallback, useEffect } from 'react'
import type { PersistedJob } from '@/types'

interface StorageSchema {
  version: number
  jobs: PersistedJob[]
}

// Separate key from the v1 frontend to avoid any cross-app interference
const STORAGE_KEY = 'cleanocr_v2_job_history_v1'
const MAX_HISTORY = 50

export function useJobPersistence() {
  const [history, setHistory] = useState<PersistedJob[]>([])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const parsed: StorageSchema = JSON.parse(raw)
      if (parsed.version !== 1 || !Array.isArray(parsed.jobs)) {
        localStorage.removeItem(STORAGE_KEY)
        return
      }
      setHistory(parsed.jobs)
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  const _saveToDisk = (jobs: PersistedJob[]) => {
    try {
      const payload: StorageSchema = { version: 1, jobs: jobs.slice(0, MAX_HISTORY) }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    } catch (e) {
      console.error('[Persistence] write failed:', e)
    }
  }

  const addOrUpdateJob = useCallback((job: PersistedJob) => {
    setHistory((prev) => {
      const idx = prev.findIndex((j) => j.id === job.id)
      let next: PersistedJob[]
      if (idx >= 0) {
        next = [...prev]
        next[idx] = { ...next[idx], ...job }
      } else {
        next = [job, ...prev]
      }
      _saveToDisk(next)
      return next
    })
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  return { history, addOrUpdateJob, clearHistory }
}
