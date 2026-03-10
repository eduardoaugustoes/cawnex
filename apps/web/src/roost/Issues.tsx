import { useEffect, useState } from "react";
import { ListChecks, ExternalLink, Circle, CheckCircle2, AlertCircle } from "lucide-react";
import { Project } from "@/lib/api";

interface Props {
  project: Project;
}

interface GHIssue {
  number: number;
  title: string;
  state: string;
  labels: string[];
  url: string;
  created_at: string;
}

export function Issues({ project }: Props) {
  const [issues, setIssues] = useState<GHIssue[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO: fetch from API once task ↔ project linking is done
    // For now, fetch from GitHub if repo is linked
    if (project.repositories.length > 0) {
      fetchIssues(project.repositories[0].github_full_name);
    } else {
      setLoading(false);
    }
  }, [project.id]);

  async function fetchIssues(repo: string) {
    try {
      // Proxy through our API would be ideal; for now show placeholder
      setLoading(false);
    } catch (e) {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-6 py-6 md:px-8 border-b border-border">
        <h2 className="text-lg font-bold">Issues</h2>
        <p className="text-xs text-text-muted mt-0.5">
          GitHub issues linked to this project
          {project.repositories.length > 0 && (
            <span className="text-text-faint"> • {project.repositories[0].github_full_name}</span>
          )}
        </p>
      </div>

      <div className="px-6 py-6 md:px-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-6 h-6 border-2 border-crow border-t-transparent rounded-full animate-spin" />
          </div>
        ) : project.repositories.length === 0 ? (
          <div className="text-center py-16">
            <ListChecks className="w-10 h-10 text-text-faint mx-auto mb-3" />
            <p className="text-sm text-text-muted">No repository linked</p>
            <p className="text-xs text-text-faint mt-1">Connect a GitHub repo to see issues here</p>
          </div>
        ) : (
          <div className="text-center py-16">
            <ListChecks className="w-10 h-10 text-text-faint mx-auto mb-3" />
            <p className="text-sm text-text-muted">Issues view coming soon</p>
            <p className="text-xs text-text-faint mt-1">
              Will pull from GitHub and link to milestones
            </p>
            {project.repositories.map(r => (
              <a
                key={r.id}
                href={`https://github.com/${r.github_full_name}/issues`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 bg-bg-surface border border-border hover:border-border-bright rounded-xl text-sm text-crow transition-smooth"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                View on GitHub
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
