import { Outlet, Link, useLocation } from "react-router-dom";
import { Bird, FolderOpen } from "lucide-react";

export function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-border px-6 py-3 flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2 text-text hover:text-primary transition-colors">
          <Bird className="w-6 h-6 text-primary" />
          <span className="text-lg font-bold tracking-tight">Cawnex</span>
        </Link>
        <span className="text-text-muted text-sm">Coordinated Intelligence</span>

        <nav className="ml-auto flex items-center gap-4">
          <Link
            to="/"
            className={`flex items-center gap-1.5 text-sm transition-colors ${
              location.pathname === "/" ? "text-primary" : "text-text-dim hover:text-text"
            }`}
          >
            <FolderOpen className="w-4 h-4" />
            Projects
          </Link>
        </nav>
      </header>

      {/* Content */}
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
