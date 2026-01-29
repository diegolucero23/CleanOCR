import { FileText, CheckCircle2, AlertCircle, Database } from "lucide-react";
import { Card } from "./ui/card";
import { ProgressBar } from "./ProgressBar";
import { cn } from "../lib/utils";
import { motion } from "framer-motion";

export type JobCardStatus = "queued" | "processing" | "completed" | "failed" | "cached";

interface JobCardProps {
    job_id: string;
    filename: string;
    status: JobCardStatus;
    progress: number;
    message?: string;
    onClick?: () => void;
}

export function JobCard({ job_id, filename, status, progress, message, onClick }: JobCardProps) {
    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ scale: 1.02 }}
            className="cursor-pointer"
            onClick={onClick}
        >
            <Card className="p-4 flex items-center gap-4 hover:shadow-md transition-shadow group">
                <div className={cn(
                    "p-3 rounded-full flex-shrink-0",
                    status === "completed" ? "bg-green-500/10 text-green-500" :
                        status === "cached" ? "bg-emerald-500/10 text-emerald-600" :
                            status === "failed" ? "bg-red-500/10 text-red-500" :
                                "bg-blue-500/10 text-primary"
                )}>
                    {status === "completed" ? <CheckCircle2 className="w-6 h-6" /> :
                        status === "cached" ? <Database className="w-6 h-6" /> :
                            status === "failed" ? <AlertCircle className="w-6 h-6" /> :
                                <FileText className="w-6 h-6" />}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-1">
                        <div className="min-w-0 pr-2">
                            <h3 className="font-semibold truncate">{filename}</h3>
                            <span className="text-xs text-muted-foreground font-mono">{job_id.slice(0, 8)}</span>
                        </div>

                        {/* Actions (Only show when complete) */}
                        {status === "completed" && (
                            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation(); // Don't trigger card click
                                        onClick?.();
                                    }}
                                    className="px-2 py-1 text-xs font-medium bg-primary/10 text-primary rounded hover:bg-primary/20"
                                >
                                    View
                                </button>
                            </div>
                        )}
                    </div>

                    {status === "processing" ? (
                        <ProgressBar progress={progress} status={message} />
                    ) : (
                        <p className={cn("text-sm truncate",
                            status === "completed" ? "text-muted-foreground" :
                                status === "failed" ? "text-destructive" : "text-muted-foreground"
                        )}>
                            {message || status}
                        </p>
                    )}
                </div>
            </Card>
        </motion.div>
    );
}
