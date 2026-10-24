import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const listProjects = () => axios.get(`${API}/projects`).then((r) => r.data);
export const getProject = (id) => axios.get(`${API}/projects/${id}`).then((r) => r.data);
export const getMessages = (id) => axios.get(`${API}/projects/${id}/messages`).then((r) => r.data);
export const deleteProject = (id) => axios.delete(`${API}/projects/${id}`);
export const analyzePage = (id, idx) => axios.post(`${API}/projects/${id}/pages/${idx}/analyze`);
export const generate3d = (id, idx) => axios.post(`${API}/projects/${id}/pages/${idx}/model3d`);
export const fetchPageImage = (id, idx) =>
  axios.get(`${API}/projects/${id}/pages/${idx}/image`, { responseType: "blob" }).then((r) => r.data);

const CHUNK = 4 * 1024 * 1024;

export async function uploadPlans(file, name, scaleHint, onProgress) {
  const { upload_id } = (await axios.post(`${API}/uploads/init`, { filename: file.name, size: file.size })).data;
  const total = Math.ceil(file.size / CHUNK);
  for (let n = 0; n < total; n++) {
    const blob = file.slice(n * CHUNK, (n + 1) * CHUNK);
    await axios.put(`${API}/uploads/${upload_id}/chunk/${n}`, blob, { headers: { "Content-Type": "application/octet-stream" } });
    onProgress(Math.round(((n + 1) / total) * 100));
  }
  return (await axios.post(`${API}/uploads/${upload_id}/complete`, { name, scale_hint: scaleHint })).data;
}

export async function streamChat(id, message, pageIndex, onDelta) {
  const res = await fetch(`${API}/projects/${id}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, page_index: pageIndex }),
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
