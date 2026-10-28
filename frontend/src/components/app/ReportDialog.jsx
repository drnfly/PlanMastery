import { useEffect, useRef, useState } from "react";
import { FileDown, Loader2, ImagePlus, X } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { getBrand, uploadLogo, deleteLogo, fetchLogo, downloadReport, runTool } from "@/lib/api";

const FIELDS = [["company_name", "Company name"], ["prepared_by", "Prepared by"], ["phone", "Phone"], ["email", "Email"], ["client", "Prepared for (client / GC)"]];
const TYPES = [["full", "Full set"], ["foundation", "Foundation crew"], ["icf", "ICF crew"], ["waterproofing", "Waterproofing crew"]];

const Toggle = ({ id, label, checked, onChange }) => (
  <label className="flex items-center justify-between text-sm text-slate-300 py-1">
    {label}<Switch data-testid={id} checked={checked} onCheckedChange={onChange} />
  </label>
);

const CrewState = ({ project, crew, onChange }) => {
  const t = project.tools?.[`crew_${crew}`] || {};
  const prepare = async () => { await runTool(project.id, `crew_${crew}`); toast.info("Preparing crew packet from the whole set…"); onChange(); };
  if (t.status === "running") return <p className="text-xs text-cyan-400 flex items-center gap-2" data-testid="crew-packet-running"><Loader2 className="h-4 w-4 animate-spin" />Preparing packet — about a minute…</p>;
  if (t.status === "ready") return (
    <p className="text-xs text-emerald-400" data-testid="crew-packet-ready">
      Packet ready · {t.data.sheets?.length || 0} sheets · {t.data.notes?.length || 0} notes ·{" "}
      <button onClick={prepare} className="underline text-slate-400 hover:text-slate-100" data-testid="crew-packet-refresh">refresh</button>
    </p>
  );
  return (
    <div className="flex items-center justify-between gap-2">
      <p className="text-xs text-slate-400">{t.status === "failed" ? `Last attempt failed: ${t.error}` : "AI picks this crew's sheets and writes their briefing, sequence, hold points and RFIs."}</p>
      <button data-testid="crew-packet-prepare-button" onClick={prepare} className="shrink-0 text-xs border border-cyan-500/50 text-cyan-300 rounded-md px-3 py-1.5 hover:bg-cyan-500/10">Prepare packet</button>
    </div>
  );
};

export const ReportDialog = ({ open, onOpenChange, project, scannedCount, onChange }) => {
  const [brand, setBrand] = useState({});
  const [logo, setLogo] = useState(null);
  const [images, setImages] = useState(true);
  const [qa, setQa] = useState(true);
  const [crew, setCrew] = useState("full");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const crewReady = crew === "full" || project.tools?.[`crew_${crew}`]?.status === "ready";

  const loadLogo = () => fetchLogo().then((b) => setLogo(URL.createObjectURL(b))).catch(() => setLogo(null));
  useEffect(() => { if (open) { getBrand().then((b) => { setBrand(b); if (b.logo_path) loadLogo(); }); } }, [open]);

  const onLogo = async (f) => {
    if (!f) return;
    try { await uploadLogo(f); loadLogo(); toast.success("Logo saved"); } catch (e) { toast.error(e.response?.data?.detail || "Logo upload failed"); }
  };

  const download = async () => {
    setBusy(true);
    try {
      const { logo_path, ...fields } = brand;
      const blob = await downloadReport(project.id, { brand: fields, include_images: images, include_qa: qa, crew });
      const suffix = crew === "full" ? "takeoff_report" : `${crew}_crew_packet`;
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${project.name.replace(/[^\w-]+/g, "_")}_${suffix}.pdf` });
      a.click();
      toast.success("Report downloaded");
      onOpenChange(false);
    } catch (e) {
      const msg = e.response?.data instanceof Blob ? JSON.parse(await e.response.data.text()).detail : "Report failed";
      toast.error(msg);
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#111827] border-slate-800 text-slate-100 max-w-lg" data-testid="report-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Takeoff report for crews</DialogTitle>
          <DialogDescription className="text-slate-400">{scannedCount} of {project.page_count} sheets scanned. Branding is saved for next time.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="grid grid-cols-4 gap-1 bg-[#0B0F17] border border-slate-800 rounded-lg p-1" data-testid="report-type-toggle">
            {TYPES.map(([k, l]) => (
              <button key={k} data-testid={`report-type-${k}`} onClick={() => setCrew(k)}
                className={`rounded-md py-1.5 text-[11px] font-medium transition-colors ${crew === k ? "bg-cyan-500 text-[#0B0F17]" : "text-slate-400 hover:text-slate-100"}`}>{l}</button>
            ))}
          </div>
          {crew !== "full" && <CrewState project={project} crew={crew} onChange={onChange} />}
          {crew === "full" && <p className="text-xs text-slate-500">Includes every scanned sheet{project.tools?.icf?.status === "ready" ? ", the ICF estimate" : ""}{project.tools?.waterproofing?.status === "ready" ? ", the waterproofing checklist" : ""}.</p>}
        </div>
        <div className="flex items-center gap-3">
          <div className="h-14 w-28 rounded-md border border-dashed border-slate-700 flex items-center justify-center bg-white/5 overflow-hidden">
            {logo ? <img src={logo} alt="logo" className="max-h-full max-w-full object-contain" data-testid="report-logo-preview" /> : <ImagePlus className="h-5 w-5 text-slate-500" />}
          </div>
          <button data-testid="report-logo-upload-button" onClick={() => fileRef.current?.click()} className="text-xs border border-slate-700 rounded-md px-3 py-1.5 hover:bg-slate-800 transition-colors">{logo ? "Change logo" : "Upload logo"}</button>
          {logo && <button data-testid="report-logo-remove-button" onClick={async () => { await deleteLogo(); setLogo(null); }} className="text-slate-500 hover:text-red-400"><X className="h-4 w-4" /></button>}
          <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg" hidden data-testid="report-logo-input" onChange={(e) => onLogo(e.target.files[0])} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          {FIELDS.map(([k, l]) => (
            <input key={k} data-testid={`report-field-${k}`} placeholder={l} value={brand[k] || ""} onChange={(e) => setBrand({ ...brand, [k]: e.target.value })}
              className={`bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 ${k === "client" ? "col-span-2" : ""}`} />
          ))}
        </div>
        <div className="border-t border-slate-800 pt-2">
          <Toggle id="report-include-images-switch" label="Include sheet images" checked={images} onChange={setImages} />
          {crew === "full" && <Toggle id="report-include-qa-switch" label="Include expert Q&A from chat" checked={qa} onChange={setQa} />}
        </div>
        <button data-testid="report-download-button" onClick={download} disabled={busy || !crewReady || (crew === "full" && !scannedCount)}
          className="w-full flex items-center justify-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold py-2.5 hover:bg-amber-400 disabled:opacity-50 active:scale-[0.98] transition-[background-color,transform]">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />} {busy ? "Building PDF…" : "Download PDF report"}
        </button>
      </DialogContent>
    </Dialog>
  );
};
