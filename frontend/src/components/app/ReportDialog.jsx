import { useEffect, useRef, useState } from "react";
import { FileDown, Loader2, ImagePlus, X } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { getBrand, uploadLogo, deleteLogo, fetchLogo, downloadReport } from "@/lib/api";

const FIELDS = [["company_name", "Company name"], ["prepared_by", "Prepared by"], ["phone", "Phone"], ["email", "Email"], ["client", "Prepared for (client / GC)"]];

const Toggle = ({ id, label, checked, onChange }) => (
  <label className="flex items-center justify-between text-sm text-slate-300 py-1">
    {label}<Switch data-testid={id} checked={checked} onCheckedChange={onChange} />
  </label>
);

export const ReportDialog = ({ open, onOpenChange, project, scannedCount }) => {
  const [brand, setBrand] = useState({});
  const [logo, setLogo] = useState(null);
  const [images, setImages] = useState(true);
  const [qa, setQa] = useState(true);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

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
      const blob = await downloadReport(project.id, { brand: fields, include_images: images, include_qa: qa });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${project.name.replace(/[^\w-]+/g, "_")}_takeoff_report.pdf` });
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
          <DialogDescription className="text-slate-400">{scannedCount} of {project.page_count} sheets scanned will be included. Branding is saved for next time.</DialogDescription>
        </DialogHeader>
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
          <Toggle id="report-include-qa-switch" label="Include expert Q&A from chat" checked={qa} onChange={setQa} />
        </div>
        <button data-testid="report-download-button" onClick={download} disabled={busy || !scannedCount}
          className="w-full flex items-center justify-center gap-2 rounded-md bg-amber-500 text-[#0B0F17] font-semibold py-2.5 hover:bg-amber-400 disabled:opacity-50 active:scale-[0.98] transition-[background-color,transform]">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />} {busy ? "Building PDF…" : "Download PDF report"}
        </button>
      </DialogContent>
    </Dialog>
  );
};
