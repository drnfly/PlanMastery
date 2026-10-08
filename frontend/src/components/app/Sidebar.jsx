import { useState } from "react";
import { Plus, Search, Trash2, FileText, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import { deleteProject } from "@/lib/api";

const STATUS = {
  analyzing: "text-cyan-400 border-cyan-500/40",
  ready: "text-emerald-400 border-emerald-500/40",
  failed: "text-red-400 border-red-500/40",
};

export const Sidebar = ({ projects, activeId, onSelect, onNew, onDeleted }) => {
  const [q, setQ] = useState("");
  const filtered = projects.filter((p) => p.name.toLowerCase().includes(q.toLowerCase()));

  const remove = async (e, id) => {
    e.stopPropagation();
    await deleteProject(id);
    onDeleted(id);
    toast.success("Project removed");
  };

  return (
    <aside data-testid="project-history-sidebar" className="col-span-12 lg:col-span-2 bg-[#111827] border border-slate-800 rounded-xl p-4 flex flex-col gap-4 lg:h-[calc(100vh-97px)] lg:sticky lg:top-[81px]">
      <button data-testid="new-project-button" onClick={onNew} className="flex items-center justify-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold text-sm py-2.5 hover:bg-amber-400 active:scale-95 transition-[background-color,transform]">
        <Plus className="h-4 w-4" /> New blueprint
      </button>
      <div className="relative">
        <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-500" />
        <input data-testid="project-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search projects"
          className="w-full bg-[#0B0F17] border border-slate-800 rounded-md pl-8 pr-2 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-cyan-500" />
      </div>
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">History</p>
      <div className="flex-1 overflow-y-auto space-y-2 -mr-2 pr-2">
        {filtered.length === 0 && <p className="text-xs text-slate-500" data-testid="no-projects-text">No projects yet.</p>}
        {filtered.map((p) => (
          <div key={p.id} role="button" data-testid={`project-item-${p.id}`} onClick={() => onSelect(p.id)}
            className={`group rounded-lg border p-3 cursor-pointer transition-colors duration-150 ${p.id === activeId ? "border-cyan-500/50 bg-slate-900/80 shadow-[0_0_15px_rgba(6,182,212,0.15)]" : "border-slate-800 hover:bg-slate-800/60 hover:border-slate-700"}`}>
            <div className="flex items-start gap-2">
              {p.ext === "pdf" ? <FileText className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" /> : <ImageIcon className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{p.name}</p>
                <p className="font-mono text-[10px] text-slate-500">{new Date(p.created_at).toLocaleDateString()}</p>
              </div>
              <button data-testid={`delete-project-${p.id}`} onClick={(e) => remove(e, p.id)} className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-500 hover:text-red-400">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            <span className={`mt-2 inline-block font-mono text-[10px] uppercase border rounded px-1.5 py-0.5 ${STATUS[p.status]}`}>{p.status}</span>
          </div>
        ))}
      </div>
    </aside>
  );
};
