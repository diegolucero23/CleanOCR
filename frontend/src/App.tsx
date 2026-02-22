import { useState, useEffect, useMemo } from 'react';
import { UploadZone } from './components/UploadZone';
import { JobCard } from './components/JobCard';
import { DiffViewer } from './components/DiffViewer';
import { uploadFile, pollJobStatus } from './lib/api';
import { useJobPersistence, type JobStatus, type PersistedJob } from './hooks/useJobPersistence';
import { OnboardingSteps } from './components/OnboardingSteps';
import { EmptyState } from './components/EmptyState';
import { LayoutDashboard, History, Trash2 } from 'lucide-react';
import { MetadataModal, type MetadataForm } from './components/MetadataModal';
import { AnimatePresence, motion } from 'framer-motion';

function App() {
  const { history, addOrUpdateJob, clearHistory } = useJobPersistence();
  const [selectedJob, setSelectedJob] = useState<PersistedJob | null>(null);
  const [metadataFile, setMetadataFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Derived State: The "Active" job is the most recent one if it's still processing
  const activeJob = useMemo(() => {
    return history.find(j => ['queued', 'processing'].includes(j.status)) || null;
  }, [history]);

  // Polling Effect: Recover ANY job that is stuck in 'queued' or 'processing'
  useEffect(() => {
    // Find all incomplete jobs
    const incompleteJobs = history.filter(j => ['queued', 'processing'].includes(j.status));

    if (incompleteJobs.length === 0) return;

    // Create a poller for each (though usually just 1)
    const timers = incompleteJobs.map(job => {
      return setInterval(async () => {
        try {
          const result = await pollJobStatus(job.id);

          // Only update if changed significantly or finished
          if (result.status !== job.status || result.progress !== job.progress) {
            addOrUpdateJob({
              ...job,
              status: result.status as JobStatus,
              progress: result.progress || 0,
              resultMessage: result.message,
              markdown: result.markdown,
              upload_time: result.upload_time,
              file_size: result.file_size,
              processing_time: result.processing_time,
              complexity: result.complexity
            });
          }
        } catch (err) {
          console.error(`Status check failed for ${job.id}`, err);
          // If it's a 404/500 repeatedly, we might want to fail it.
          // For now, let it retry indefinitely or until user clears.
        }
      }, 1000);
    });

    return () => timers.forEach(clearInterval);
  }, [history, addOrUpdateJob]);
  // Note: history dependency might cause re-creation of intervals on every progress update.
  // Ideally we use a ref or a more granular approach, but for <5 active jobs this is fine.
  // The 'addOrUpdateJob' is stable.

  const handleFileSelect = (file: File) => {
    setMetadataFile(file); // Triggers Modal
  };

  const handleProcess = async (file: File, meta?: MetadataForm, skip = false) => {
    setMetadataFile(null); // Close Modal
    setIsUploading(true);

    try {
      // 1. Upload
      const response = await uploadFile(file, meta, skip);

      // 2. Add Job
      const realJob: PersistedJob = {
        id: response.job_id,
        uploaded_filename: file.name,
        status: 'queued',
        progress: 0,
        timestamp: Date.now(),
        resultMessage: 'Upload complete. Waiting for worker...'
      };

      addOrUpdateJob(realJob);

    } catch (error) {
      console.error(error);
      alert("Upload Failed");
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
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>v1.2.0 (Resilient)</span>
            <div className="w-px h-4 bg-border" />
            {history.length > 0 && (
              <button onClick={clearHistory} className="flex items-center gap-1 hover:text-destructive transition-colors">
                <Trash2 className="w-4 h-4" /> Clear History
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 space-y-12">

        {/* Hero / Upload Section */}
        <section className="flex flex-col items-center space-y-8">
          <div className="text-center space-y-2 mb-4">
            <h2 className="text-3xl font-bold">New Extraction Job</h2>
            <p className="text-muted-foreground">Upload a PDF. Your jobs are saved automatically.</p>
          </div>

          <OnboardingSteps />

          <UploadZone onFileSelect={handleFileSelect} isUploading={isUploading} />

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
                  job_id={activeJob.id}
                  filename={activeJob.uploaded_filename}
                  status={activeJob.status}
                  progress={activeJob.progress}
                  message={activeJob.resultMessage}
                  file_size={activeJob.file_size}
                  processing_time={activeJob.processing_time}
                  complexity={activeJob.complexity}
                  onClick={() => activeJob.status === 'completed' && setSelectedJob(activeJob)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* History Section */}
        <section className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center gap-2 pb-4 border-b">
            <History className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Recent Jobs ({history.length})</h2>
          </div>

          <AnimatePresence mode="popLayout">
            {history.length === 0 ? (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <EmptyState />
              </motion.div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {history.map((job) => (
                  <JobCard
                    key={job.id}
                    job_id={job.id}
                    filename={job.uploaded_filename}
                    status={job.status}
                    progress={job.progress}
                    message={job.resultMessage}
                    file_size={job.file_size}
                    processing_time={job.processing_time}
                    complexity={job.complexity}
                    onClick={() => job.status === 'completed' && setSelectedJob(job)}
                  />
                ))}
              </div>
            )}
          </AnimatePresence>
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
    </div>
  );
}

export default App;
