import { useState, useEffect } from 'react';
import { UploadZone } from './components/UploadZone';
import { JobCard } from './components/JobCard';
import { DiffViewer } from './components/DiffViewer';
import { uploadFile, pollJobStatus, type JobResponse } from './lib/api';
import { LayoutDashboard, History } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

// Mock History Data
const MOCK_HISTORY = [
  { job_id: 'mock-1', filename: 'invoice_jan_2025.pdf', status: 'completed', progress: 100 },
  { job_id: 'mock-2', filename: 'scanned_contract.pdf', status: 'completed', progress: 100 },
] as const;

// Combined type for UI state
interface Job extends Omit<JobResponse, 'status'> {
  filename: string;
  progress: number;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  message?: string;
}

function App() {
  const [activeJob, setActiveJob] = useState<Job | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [history, setHistory] = useState<Job[]>([...MOCK_HISTORY]);

  // Polling Hook
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    if (activeJob && ['queued', 'processing'].includes(activeJob.status)) {
      interval = setInterval(async () => {
        try {
          const status = await pollJobStatus(activeJob.job_id);

          setActiveJob(prev => {
            if (!prev) return null;

            // Merge current state with API updates
            const newState = {
              ...prev,
              status: status.status as Job['status'],
              progress: status.progress || 0,
              message: status.message || prev.message
            };

            return newState;
          });

          // Check if done to stop polling early interaction-wise
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(interval);
            // Add to history
            setHistory(prev => {
              // Avoid duplicates if possible
              if (prev.some(j => j.job_id === activeJob.job_id)) return prev;
              // Create completed job object
              const completedJob = {
                ...activeJob,
                status: status.status as Job['status'],
                progress: status.status === 'completed' ? 100 : status.progress || 0,
                message: status.message
              };
              return [completedJob, ...prev];
            });
          }

        } catch (error) {
          console.error("Polling failed", error);
        }
      }, 1000); // Poll every 1s
    }

    return () => clearInterval(interval);
  }, [activeJob?.status, activeJob?.job_id]);

  const handleUpload = async (file: File) => {
    try {
      // Optimistic UI
      const newJob: Job = {
        job_id: 'pending...',
        filename: file.name,
        status: 'queued',
        progress: 0,
        message: 'Uploading...'
      };
      setActiveJob(newJob);

      const response = await uploadFile(file);

      // Update with real ID - this triggers the Polling Effect
      setActiveJob(prev => prev ? {
        ...prev,
        job_id: response.job_id,
        status: 'queued',
        message: 'Upload complete. Waiting for worker...'
      } : null);

    } catch (error) {
      console.error(error);
      setActiveJob(prev => prev ? { ...prev, status: 'failed', message: 'Upload failed' } : null);
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
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>v1.1.0</span>
            <div className="w-px h-4 bg-border" />
            <span>Connected</span>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-12">

        {/* Hero / Upload Section */}
        <section className="space-y-8">
          <div className="text-center space-y-2">
            <h2 className="text-3xl font-bold">New Extraction Job</h2>
            <p className="text-muted-foreground">Upload a PDF to extract clean Markdown with high accuracy.</p>
          </div>

          <UploadZone onFileSelect={handleUpload} isUploading={activeJob?.status === 'processing' || activeJob?.status === 'queued'} />

          {/* Active Job Status */}
          <AnimatePresence>
            {activeJob && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="max-w-xl mx-auto"
              >
                <JobCard
                  {...activeJob}
                  job_id={activeJob.job_id}
                  onClick={() => activeJob.status === 'completed' && setShowDiff(true)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* History Section */}
        <section className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center gap-2 pb-4 border-b">
            <History className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Recent Jobs</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {history.map((job, i) => (
              <JobCard
                key={job.job_id || i}
                {...job}
                job_id={job.job_id}
                onClick={() => job.status === 'completed' && setShowDiff(true)}
              />
            ))}
          </div>
        </section>

      </main>

      {/* Modals */}
      <AnimatePresence>
        {showDiff && (
          <DiffViewer onClose={() => setShowDiff(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
