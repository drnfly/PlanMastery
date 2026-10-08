import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const listProjects = () => axios.get(`${API}/projects`).then((r) => r.data);
export const getProject = (id) => axios.get(`${API}/projects/${id}`).then((r) => r.data);
export const getMessages = (id) => axios.get(`${API}/projects/${id}/messages`).then((r) => r.data);
export const deleteProject = (id) => axios.delete(`${API}/projects/${id}`);
export const reanalyze = (id) => axios.post(`${API}/projects/${id}/reanalyze`);
export const fetchFileBlob = (id) =>
  axios.get(`${API}/projects/${id}/file`, { responseType: "blob" }).then((r) => r.data);

export const createProject = (file, name, scaleHint) => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", name);
  fd.append("scale_hint", scaleHint);
  return axios.post(`${API}/projects`, fd).then((r) => r.data);
};

export async function streamChat(id, message, onDelta) {
  const res = await fetch(`${API}/projects/${id}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Chat failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      if (!p.startsWith("data: ")) continue;
      const ev = JSON.parse(p.slice(6));
      if (ev.error) throw new Error(ev.error);
      if (ev.delta) onDelta(ev.delta);
    }
  }
}
