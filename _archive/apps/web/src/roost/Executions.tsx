import { Zap, Clock } from "lucide-react";

export function Executions() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-6 py-6 md:px-8 border-b border-border">
        <h2 className="text-lg font-bold">Executions</h2>
        <p className="text-xs text-text-muted mt-0.5">Live agent runs and history</p>
      </div>

      <div className="px-6 py-6 md:px-8">
        <div className="text-center py-16">
          <div className="w-14 h-14 rounded-2xl bg-bg-surface flex items-center justify-center mx-auto mb-4">
            <Zap className="w-7 h-7 text-text-faint" />
          </div>
          <p className="text-sm text-text-muted">No executions yet</p>
          <p className="text-xs text-text-faint mt-1 max-w-xs mx-auto">
            When crows start working on issues, their execution logs will appear here in real time.
          </p>
          <div className="mt-6 flex items-center justify-center gap-2 text-xs text-text-faint">
            <Clock className="w-3.5 h-3.5" />
            Waiting for first run...
          </div>
        </div>
      </div>
    </div>
  );
}
