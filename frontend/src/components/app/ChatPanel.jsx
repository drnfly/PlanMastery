import { useEffect, useRef, useState } from "react";
import { Send, Bot, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { getMessages, streamChat } from "@/lib/api";
import { Markdown } from "@/components/app/Markdown";

const PROMPTS = ["What is the total square footage?", "Is this foundation suitable for ICF walls?", "Review the waterproofing at the foundation", "Size the header over the widest opening"];

export const ChatPanel = ({ project, page }) => {
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  const ready = project?.status === "ready";

  useEffect(() => { setMsgs([]); if (project?.id) getMessages(project.id).then(setMsgs); }, [project?.id]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy || !ready) return;
    setInput(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    try {
      await streamChat(project.id, q, page?.index ?? 0, (d) => setMsgs((m) => {
        const copy = [...m]; copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + d }; return copy;
      }));
    } catch (e) {
      toast.error(e.message);
      setMsgs((m) => m.slice(0, -1));
    } finally { setBusy(false); }
  };

  return (
    <aside data-testid="chat-panel-container" className="col-span-12 lg:col-span-3 bg-[#111827] border border-slate-800 rounded-xl flex flex-col h-[640px] lg:h-[calc(100vh-97px)] lg:sticky lg:top-[81px]">
      <div className="px-4 py-3 border-b border-slate-800">
        <div className="flex items-center gap-2"><Bot className="h-4 w-4 text-cyan-400" /><p className="font-display font-semibold text-sm">Plan expert</p></div>
        <p className="font-mono text-[10px] text-slate-500 mt-1" data-testid="chat-expert-roles">Structural · Architect · ICF · Waterproofing</p>
        {page && <p className="text-[11px] text-amber-400/90 mt-1 truncate" data-testid="chat-current-sheet">Viewing: {page.sheet_number ? `${page.sheet_number} ` : ""}{page.title}</p>}
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="chat-message-list">
        {!project && <p className="text-xs text-slate-500">Upload or select a plan set to start asking questions.</p>}
        {project && !ready && <p className="text-xs text-slate-500">Chat unlocks once the sheets are processed.</p>}
        {ready && msgs.length === 0 && (
          <div className="space-y-2">
            <p className="text-xs text-slate-500 mb-2">Try asking:</p>
            {PROMPTS.map((p, i) => (
              <button key={p} data-testid={`suggested-prompt-chip-${i}`} onClick={() => send(p)} className="block w-full text-left text-xs border border-slate-800 rounded-md px-3 py-2 text-slate-300 hover:border-cyan-500/50 hover:bg-slate-800/50 transition-colors">{p}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} data-testid={`chat-message-${m.role}`} className={`fade-up text-sm rounded-lg px-3 py-2.5 ${m.role === "user" ? "bg-amber-500/10 border border-amber-500/30 ml-6" : "bg-[#0B0F17] border border-slate-800 mr-2 text-slate-300"}`}>
            {m.role === "assistant" && !m.content ? <Loader2 className="h-4 w-4 animate-spin text-cyan-400" /> : m.role === "assistant" ? <Markdown text={m.content} /> : m.content}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="p-3 border-t border-slate-800 flex gap-2">
        <textarea data-testid="chat-input-textarea" rows={2} value={input} disabled={!ready} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={ready ? "Ask anything about these plans…" : "Waiting for plans"}
          className="flex-1 resize-none bg-[#0B0F17] border border-slate-800 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50" />
        <button data-testid="chat-send-button" onClick={() => send()} disabled={!ready || busy || !input.trim()}
          className="self-end h-10 w-10 flex items-center justify-center rounded-md bg-amber-500 text-[#0B0F17] hover:bg-amber-400 disabled:opacity-40 active:scale-95 transition-[background-color,transform]">
          <Send className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
};
