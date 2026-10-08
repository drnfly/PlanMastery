import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Ruler } from "lucide-react";
import { listProjects, getProject } from "@/lib/api";
import { Sidebar } from "@/components/app/Sidebar";
import { UploadPanel } from "@/components/app/UploadPanel";
import { BlueprintViewer } from "@/components/app/BlueprintViewer";
import { DimensionTable } from "@/components/app/DimensionTable";
import { ChatPanel } from "@/components/app/ChatPanel";
import { AnalysisSummary } from "@/components/app/AnalysisSummary";

export default function Workspace() {
  const [projects, setProjects] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [project, setProject] = useState(null);

  const refreshList = useCallback(() => listProjects().then(setProjects).catch(() => toast.error("Could not load projects")), []);

  useEffect(() => { refreshList(); }, [refreshList]);

  useEffect(() => {
    if (!activeId) { setProject(null); return; }
    let timer;
    const load = async () => {
      const p = await getProject(activeId).catch(() => null);
      if (!p) return;
      setProject(p);
      if (p.status === "analyzing") timer = setTimeout(load, 4000);
      else refreshList();
    };
    load();
    return () => clearTimeout(timer);
  }, [activeId, refreshList]);

  const onCreated = (p) => { setProjects((prev) => [p, ...prev]); setActiveId(p.id); };
  const onDeleted = (id) => { setProjects((prev) => prev.filter((x) => x.id !== id)); if (id === activeId) setActiveId(null); };

  return (
    <div className="min-h-screen" data-testid="workspace">
      <header className="sticky top-0 z-40 bg-[#0B0F17]/90 backdrop-blur-md border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-md bg-amber-500 flex items-center justify-center"><Ruler className="h-4 w-4 text-[#0B0F17]" /></div>
          <span className="font-display text-lg font-semibold tracking-tight">BuildSpec<span className="text-amber-500">.ai</span></span>
          <span className="hidden sm:inline font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 border border-slate-800 rounded px-2 py-0.5">Gemini 3.1 Pro · Vision</span>
        </div>
        <span className="font-mono text-xs text-slate-500 hidden md:inline">{projects.length} projects</span>
      </header>
      <main className="grid grid-cols-1 lg:grid-cols-12 gap-4 p-4">
        <Sidebar projects={projects} activeId={activeId} onSelect={setActiveId} onNew={() => setActiveId(null)} onDeleted={onDeleted} />
        <section className="col-span-12 lg:col-span-7 flex flex-col gap-4 min-w-0">
          {!project ? <UploadPanel onCreated={onCreated} /> : (
            <>
              <BlueprintViewer project={project} />
              <AnalysisSummary project={project} onReanalyze={() => setProject({ ...project, status: "analyzing" })} />
              <DimensionTable project={project} />
            </>
          )}
        </section>
        <ChatPanel project={project} />
      </main>
    </div>
  );
}
