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
    file_size?: number;
    processing_time?: number;
    complexity?: number;
    onClick?: () => void;
}

export function JobCard({ job_id, filename, status, progress, message, file_size, processing_time, complexity, onClick }: JobCardProps) {
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

                    {status === "completed" && (
                        <div className="flex gap-2 mt-2 flex-wrap">
                            {file_size && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-secondary text-secondary-foreground border">
                                    {(file_size / (1024 * 1024)).toFixed(1)} MB
                                </span>
                            )}
                            {processing_time && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-secondary text-secondary-foreground border">
                                    {processing_time > 60 ? `${Math.floor(processing_time / 60)}m ${Math.floor(processing_time % 60)}s` : `${Math.floor(processing_time)}s`}
                                </span>
                            )}
                            {complexity && (
                                <span className={cn(
                                    "px-2 py-0.5 rounded-full text-[10px] font-medium border",
                                    complexity < 4 ? "bg-green-500/10 text-green-600 border-green-500/20" :
                                        complexity < 7 ? "bg-yellow-500/10 text-yellow-600 border-yellow-500/20" :
                                            "bg-red-500/10 text-red-600 border-red-500/20"
                                )}>
                                    Complexity: {complexity.toFixed(1)}
                                </span>
                            )}
                        </div>
                    )}
                </div>
            </Card>
        </motion.div>
    );
}
