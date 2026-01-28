import { FileText, CheckCircle2, AlertCircle } from "lucide-react";
import { Card } from "./ui/card";
import { ProgressBar } from "./ProgressBar";
import { cn } from "../lib/utils";
import { motion } from "framer-motion";

interface JobCardProps {
    job_id: string;
    filename: string;
    status: "queued" | "processing" | "completed" | "failed";
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
            <Card className="p-4 flex items-center gap-4 hover:shadow-md transition-shadow">
                <div className={cn(
                    "p-3 rounded-full flex-shrink-0",
                    status === "completed" ? "bg-green-500/10 text-green-500" :
                        status === "failed" ? "bg-red-500/10 text-red-500" :
                            "bg-blue-500/10 text-primary"
                )}>
                    {status === "completed" ? <CheckCircle2 className="w-6 h-6" /> :
                        status === "failed" ? <AlertCircle className="w-6 h-6" /> :
                            <FileText className="w-6 h-6" />}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-1">
                        <h3 className="font-semibold truncate pr-2">{filename}</h3>
                        <span className="text-xs text-muted-foreground font-mono">{job_id.slice(0, 8)}</span>
                    </div>

                    {status === "processing" ? (
                        <ProgressBar progress={progress} status={message} />
                    ) : (
                        <p className={cn("text-sm",
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
