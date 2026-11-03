import { useState, useEffect, useRef, useMemo } from 'react';
import { UploadZone } from './components/UploadZone';
import { JobCard } from './components/JobCard';
import { DiffViewer } from './components/DiffViewer';
import { JobHistory } from './components/JobHistory';
import { uploadFile, subscribeToJobStatus, fetchLimits, pollJobStatus, type IngestionLimits } from './lib/api';
import { useJobPersistence, type JobStatus, type PersistedJob } from './hooks/useJobPersistence';
import { OnboardingSteps } from './components/OnboardingSteps';
import { LayoutDashboard, History, Trash2, Key } from 'lucide-react';
import { MetadataModal, type MetadataForm } from './components/MetadataModal';
import { SettingsModal } from './components/SettingsModal';
import { NotificationToastContainer, type ToastNotification } from './components/NotificationToast';
import { AnimatePresence, motion } from 'framer-motion';

function App() {
  const { history, addOrUpdateJob, clearHistory } = useJobPersistence();
  const [selectedJob, setSelectedJob] = useState<PersistedJob | null>(null);
  const [metadataFile, setMetadataFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [limits, setLimits] = useState<IngestionLimits | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const addToast = (toast: ToastNotification) => {
    setToasts((prev) => [...prev.filter((t) => t.id !== toast.id), toast]);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Fetch server-disclosed ingestion limits once, so the upload UI shows
  // the caps the backend actually enforces.
  useEffect(() => {
    fetchLimits()
      .then(setLimits)
      .catch((e) => console.warn('Could not fetch ingestion limits:', e));
  }, []);

  // Derived State: The "Active" job is the most recent one if it's still processing
  const activeJob = useMemo(() => {
    return history.find(j => ['queued', 'processing'].includes(j.status)) || null;
  }, [history]);

  // SSE Effect: open one EventSource per active job
  const activeStreams = useRef<Map<string, () => void>>(new Map());
  const timedOutStreams = useRef<Set<string>>(new Set());

  useEffect(() => {
    const incompleteIds = new Set(
      history
        .filter(j => ['queued', 'processing'].includes(j.status) && !timedOutStreams.current.has(j.id))
        .map(j => j.id)
    );

    // Close streams for jobs that are no longer active
    activeStreams.current.forEach((close, jobId) => {
      if (!incompleteIds.has(jobId)) {
        close();
        activeStreams.current.delete(jobId);
      }
    });

    // Open streams for newly discovered active jobs
    history
      .filter(j => incompleteIds.has(j.id) && !activeStreams.current.has(j.id))
      .forEach(job => {
        const close = subscribeToJobStatus(
          job.id,
          (result) => {
            if (result.status === 'stream_timeout') {
              timedOutStreams.current.add(job.id);
              activeStreams.current.delete(job.id);
              pollJobStatus(job.id)
                .then((latest) => {
                  const stillRunning = ['queued', 'processing'].includes(latest.status);
                  addOrUpdateJob({
                    ...job,
                    status: latest.status as JobStatus,
                    progress: latest.progress || job.progress,
                    resultMessage: stillRunning
                      ? 'Live view expired — the job is still running in the background. Refresh the page to check on it.'
                      : latest.message,
                    markdown: latest.markdown,
                    processing_time: latest.processing_time,
                    complexity: latest.complexity,
                  });
                })
                .catch((e) => console.warn(`Post-timeout status poll failed for ${job.id}`, e));
              return;
            }
            addOrUpdateJob({
              id: job.id,
              uploaded_filename: job.uploaded_filename,
              timestamp: job.timestamp,
              status: result.status as JobStatus,
              progress: result.progress || 0,
              resultMessage: result.message,
              markdown: result.markdown,
              upload_time: result.upload_time,
              file_size: result.file_size,
              processing_time: result.processing_time,
              complexity: result.complexity,
            });
            if (result.status === 'completed' || result.status === 'failed') {
              activeStreams.current.delete(job.id);
              // Trigger refresh of persistent history list on completion
              setHistoryRefreshKey((k) => k + 1);
            }
          },
          (err) => console.error(`SSE error for ${job.id}`, err),
        );
        activeStreams.current.set(job.id, close);
      });

  }, [history, addOrUpdateJob]);

  useEffect(() => {
    return () => {
      activeStreams.current.forEach(close => close());
      activeStreams.current.clear();
    };
  }, []);

  const handleFileSelect = (file: File) => {
    setMetadataFile(file);
  };

  const handleProcess = async (file: File, meta?: MetadataForm, skip = false) => {
    setMetadataFile(null);
    setIsUploading(true);

    try {
      // 1. Upload
      const response = await uploadFile(file, meta, skip);

      // 2. Add Job to in-memory active list
      const realJob: PersistedJob = {
        id: response.job_id,
        uploaded_filename: file.name,
        status: 'queued',
        progress: 0,
        timestamp: Date.now(),
        resultMessage: 'Upload complete. Waiting for worker...',
        page_count: response.expectations?.page_count,
        expected_seconds: response.expectations?.stream_timeout_seconds,
      };

      addOrUpdateJob(realJob);
      setHistoryRefreshKey((k) => k + 1);

      addToast({
        id: `toast-success-${Date.now()}`,
        type: 'success',
        title: 'Upload Queued',
        message: `Successfully queued "${file.name}" for extraction.`,
        durationMs: 3500,
      });

    } catch (error: any) {
      console.error('Upload failed:', error);
      const status = error.response?.status;
      const errorData = error.response?.data?.error;
      const code = errorData?.code;
      const message = errorData?.message || (typeof error.response?.data === 'string' ? error.response.data : error.message) || 'Upload Failed';
      const retryAfter = errorData?.details?.retry_after_seconds || (error.response?.headers?.['retry-after'] ? parseInt(error.response.headers['retry-after'], 10) : undefined);

      if (status === 401) {
        addToast({
          id: `toast-${Date.now()}`,
          type: 'error',
          code: 'UNAUTHORIZED',
          title: 'Authentication Required',
          message: message || 'A valid CleanOCR API key is required to submit extraction jobs.',
          actionLabel: 'Configure API Key',
          onAction: () => setIsSettingsOpen(true),
        });
      } else if (status === 429) {
        addToast({
          id: `toast-${Date.now()}`,
          type: 'warning',
          code: 'RATE_LIMIT_EXCEEDED',
          title: 'Upload Rate Limit Exceeded',
          message: message || 'You have exceeded the upload quota. Please wait before retrying.',
          retryAfterSeconds: retryAfter || 20,
        });
      } else if (status === 413) {
        addToast({
          id: `toast-${Date.now()}`,
          type: 'error',
          code: 'FILE_TOO_LARGE',
          title: 'File Too Large',
          message: message || 'The selected file exceeds the maximum permitted upload size.',
        });
      } else {
        addToast({
          id: `toast-${Date.now()}`,
          type: 'error',
          code: code || 'UPLOAD_FAILED',
          title: 'Upload Failed',
          message: message || 'Failed to submit extraction job. Please check connection and retry.',
        });
      }
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground font-sans selection:bg-primary/20">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-primary/10 rounded-lg">
              <LayoutDashboard className="w-6 h-6 text-primary" />
            </div>
            <h1 className="text-xl font-bold tracking-tight">CleanOCR <span className="text-primary">Console</span></h1>
          </div>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border/80 hover:bg-muted text-foreground transition-colors text-xs font-medium"
              title="API Key Settings"
            >
              <Key className="w-3.5 h-3.5 text-primary" />
              <span>API Key</span>
            </button>
            <div className="hidden sm:block w-px h-4 bg-border" />
            <span className="hidden sm:inline">v1.2.0 (Resilient)</span>
            {history.length > 0 && (
              <>
                <div className="w-px h-4 bg-border" />
                <button onClick={clearHistory} className="flex items-center gap-1 hover:text-destructive transition-colors text-xs" title="Clear Local Cache">
                  <Trash2 className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Clear Local</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-12">

        {/* Hero / Upload Section */}
        <section className="flex flex-col items-center space-y-8">
          <div className="text-center space-y-2 mb-4">
            <h2 className="text-3xl font-bold">New Extraction Job</h2>
            <p className="text-muted-foreground">Upload a PDF. Your extraction jobs are permanently persisted in the relational database.</p>
          </div>

          <OnboardingSteps />

          <UploadZone onFileSelect={handleFileSelect} isUploading={isUploading} limits={limits} />

          {/* Active Job Real-Time Card */}
          <AnimatePresence>
            {activeJob && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="w-full max-w-xl mx-auto"
              >
                <JobCard
                  job_id={activeJob.id}
                  filename={activeJob.uploaded_filename}
                  status={activeJob.status}
                  progress={activeJob.progress}
                  message={activeJob.resultMessage}
                  file_size={activeJob.file_size}
                  processing_time={activeJob.processing_time}
                  complexity={activeJob.complexity}
                  page_count={activeJob.page_count}
                  expected_seconds={activeJob.expected_seconds}
                  onClick={() => activeJob.status === 'completed' && setSelectedJob(activeJob)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Persistent History Section (Set B: Relational DB Engine) */}
        <section className="max-w-4xl mx-auto space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-border/70">
            <History className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold tracking-tight">Database Job History</h2>
          </div>

          <JobHistory
            key={historyRefreshKey}
            onSelectJob={(job) => setSelectedJob(job)}
            onError={(msg, code) => addToast({
              id: `toast-history-${Date.now()}`,
              type: 'warning',
              code: code || 'DATABASE_NOTICE',
              title: 'History Notice',
              message: msg,
            })}
            currentActiveJobId={activeJob?.id}
          />
        </section>

      </main>

      {/* Modals */}
      <AnimatePresence>
        {selectedJob && (
          <DiffViewer
            job_id={selectedJob.id}
            markdown={selectedJob.markdown}
            file_size={selectedJob.file_size}
            processing_time={selectedJob.processing_time}
            complexity={selectedJob.complexity}
            onClose={() => setSelectedJob(null)}
          />
        )}
      </AnimatePresence>

      {/* Metadata Modal */}
      <MetadataModal
        isOpen={!!metadataFile}
        filename={metadataFile?.name || ''}
        onClose={() => setMetadataFile(null)}
        onConfirm={(data) => handleProcess(metadataFile!, data)}
        onSkip={() => handleProcess(metadataFile!, undefined, true)}
      />

      {/* Security & Access Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

      {/* Global Notifications & Rate Limit Countdown Toasts */}
      <NotificationToastContainer
        notifications={toasts}
        onDismiss={dismissToast}
      />
    </div>
  );
}

export default App;
