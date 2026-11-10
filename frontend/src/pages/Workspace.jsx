import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Ruler, Loader2, AlertTriangle, Layers, Boxes, Droplets, Camera, Waves } from "lucide-react";
import { listProjects, getProject, analyzePage } from "@/lib/api";
import { Sidebar } from "@/components/app/Sidebar";
import { UploadPanel } from "@/components/app/UploadPanel";
import { BlueprintViewer } from "@/components/app/BlueprintViewer";
import { DimensionTable } from "@/components/app/DimensionTable";
import { ChatPanel } from "@/components/app/ChatPanel";
import { AnalysisSummary } from "@/components/app/AnalysisSummary";
import { SheetStrip } from "@/components/app/SheetStrip";
import { SetToolbar } from "@/components/app/SetToolbar";
import { IcfEstimator } from "@/components/app/IcfEstimator";
import { WaterproofingChecklist, DrainagePlan } from "@/components/app/WaterproofingChecklist";
import { PhotosPanel } from "@/components/app/PhotosPanel";

const TABS = [["sheets", "Sheets", Layers], ["icf", "ICF estimator", Boxes], ["waterproofing", "Waterproofing", Droplets], ["drainage", "Drainage", Waves], ["photos", "Job photos", Camera]];

const busy = (p, i) => p.status === "processing" || p.pages?.some((pg) => pg.status === "analyzing" || pg.model3d_status === "generating" || pg.drain_status === "generating")
  || p.pages?.[i]?.status === "pending" || Object.values(p.tools || {}).some((t) => t.status === "running");

export default function Workspace() {
  const [params] = useSearchParams();
  const [projects, setProjects] = useState([]);
  const [activeId, setActiveId] = useState(params.get("project"));
  const [project, setProject] = useState(null);
  const [pageIdx, setPageIdx] = useState(0);
  const [tick, setTick] = useState(0);
  const [view, setView] = useState(params.get("tab") || "sheets");
  const prevId = useRef(activeId);

  const refreshList = useCallback(() => listProjects().then(setProjects).catch(() => toast.error("Could not load projects")), []);
  const poke = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => { refreshList(); }, [refreshList]);
  useEffect(() => {
    if (prevId.current === activeId) return;
    prevId.current = activeId;
    setPageIdx(0); setView("sheets");
  }, [activeId]);

  useEffect(() => {
    if (!activeId) { setProject(null); return; }
    let timer;
    let stop = false;
    const load = async () => {
      const p = await getProject(activeId).catch(() => null);
      if (!p || stop) return;
      setProject((prev) => { if (prev?.id === p.id && prev.status !== p.status) refreshList(); return p; });
      const pg = p.pages?.[pageIdx];
      if (p.status === "ready" && pg?.status === "pending") { await analyzePage(p.id, pg.index); timer = setTimeout(load, 1000); return; }
      if (busy(p, pageIdx)) timer = setTimeout(load, 3500);
      else refreshList();
    };
    load();
    return () => { stop = true; clearTimeout(timer); };
  }, [activeId, pageIdx, tick, refreshList]);

  const onCreated = (p) => { setProjects((prev) => [p, ...prev]); setActiveId(p.id); };
  const onDeleted = (id) => { setProjects((prev) => prev.filter((x) => x.id !== id)); if (id === activeId) setActiveId(null); };
  const page = project?.pages?.[pageIdx];

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
          {!project ? <UploadPanel onCreated={onCreated} /> : project.status === "processing" || !page ? (
            <div className="bg-[#111827] border border-slate-800 rounded-xl p-8 flex items-center gap-4" data-testid="processing-panel">
              {project.status === "failed" ? <AlertTriangle className="h-6 w-6 text-red-400" /> : <Loader2 className="h-6 w-6 animate-spin text-cyan-400" />}
              <div>
                <p className="font-display font-semibold" data-testid="processing-status-text">{project.status === "failed" ? project.error : "Splitting and indexing sheets…"}</p>
                {project.status === "failed"
                  ? <p className="text-xs text-slate-500 mt-1">Delete this project from the sidebar and upload the file again.</p>
                  : <p className="font-mono text-xs text-slate-500 mt-1" data-testid="processing-progress">{project.processed_pages || 0} / {project.page_count || "?"} sheets processed</p>}
              </div>
            </div>
          ) : (
            <>
              <SetToolbar project={project} onChange={poke} />
              <div className="flex gap-1 bg-[#111827] border border-slate-800 rounded-xl p-1 overflow-x-auto" data-testid="project-tabs">
                {TABS.map(([k, l, Icon]) => (
                  <button key={k} data-testid={`project-tab-${k}`} onClick={() => setView(k)}
                    className={`flex-1 min-w-max flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${view === k ? "bg-amber-500 text-[#0B0F17]" : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"}`}>
                    <Icon className="h-4 w-4" />{l}{project.tools?.[k]?.status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  </button>
                ))}
              </div>
              {view === "sheets" && (
                <>
                  <SheetStrip pages={project.pages} active={pageIdx} onSelect={setPageIdx} />
                  <BlueprintViewer project={project} page={page} onChange={poke} />
                  <AnalysisSummary project={project} page={page} onChange={poke} />
                  <DimensionTable project={project} page={page} />
                </>
              )}
              {view === "icf" && <IcfEstimator project={project} onChange={poke} />}
              {view === "waterproofing" && <WaterproofingChecklist project={project} onChange={poke} />}
              {view === "drainage" && <DrainagePlan project={project} onChange={poke} />}
              {view === "photos" && <PhotosPanel project={project} />}
            </>
          )}
        </section>
        <ChatPanel project={project} page={page} />
      </main>
    </div>
  );
}
