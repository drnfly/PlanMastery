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

export const scanSet = (id) => axios.post(`${API}/projects/${id}/scan`).then((r) => r.data);
export const getBrand = () => axios.get(`${API}/settings/brand`).then((r) => r.data);
export const uploadLogo = (file) => { const fd = new FormData(); fd.append("file", file); return axios.post(`${API}/settings/brand/logo`, fd); };
export const deleteLogo = () => axios.delete(`${API}/settings/brand/logo`);
export const fetchLogo = () => axios.get(`${API}/settings/brand/logo`, { responseType: "blob" }).then((r) => r.data);
export const downloadReport = (id, body) =>
  axios.post(`${API}/projects/${id}/report`, body, { responseType: "blob" }).then((r) => r.data);
export const runTool = (id, tool) => axios.post(`${API}/projects/${id}/tools/${tool}`);
export const editIcf = (id, body) => axios.put(`${API}/projects/${id}/tools/icf`, body).then((r) => r.data);
export const patchWp = (id, i, verified, tool = "waterproofing") => axios.patch(`${API}/projects/${id}/tools/${tool}/items/${i}`, { verified });
export const listPhotos = (id) => axios.get(`${API}/projects/${id}/photos`).then((r) => r.data);
export const uploadPhoto = (id, file, note) => {
  const fd = new FormData(); fd.append("file", file); fd.append("note", note);
  return axios.post(`${API}/projects/${id}/photos`, fd).then((r) => r.data);
};
export const fetchPhoto = (pid) => axios.get(`${API}/photos/${pid}/image`, { responseType: "blob" }).then((r) => r.data);
export const askPhoto = (pid, question) => axios.post(`${API}/photos/${pid}/ask`, { question });
export const reanalyzePhoto = (pid) => axios.post(`${API}/photos/${pid}/reanalyze`);
export const deletePhoto = (pid) => axios.delete(`${API}/photos/${pid}`);
export const startDrainOverlay = (id, idx) => axios.post(`${API}/projects/${id}/pages/${idx}/drain-overlay`);
export const editDrainOverlay = (id, idx, body) => axios.put(`${API}/projects/${id}/pages/${idx}/drain-overlay`, body).then((r) => r.data);
export const fetchDrainPng = (id, idx) =>
  axios.get(`${API}/projects/${id}/pages/${idx}/drain-overlay.png`, { responseType: "blob" }).then((r) => r.data);

const CHUNK = 4 * 1024 * 1024;

const putChunk = async (url, blob, tries = 4) => {
  for (let i = 0; ; i++) {
    try { return await axios.put(url, blob, { headers: { "Content-Type": "application/octet-stream" } }); }
    catch (e) { if (i >= tries - 1 || (e.response && e.response.status < 500)) throw e; await new Promise((r) => setTimeout(r, 1000 * 2 ** i)); }
  }
};

export async function uploadPlans(file, name, scaleHint, onProgress) {
  const { upload_id } = (await axios.post(`${API}/uploads/init`, { filename: file.name, size: file.size })).data;
  const total = Math.ceil(file.size / CHUNK);
  for (let n = 0; n < total; n++) {
    await putChunk(`${API}/uploads/${upload_id}/chunk/${n}`, file.slice(n * CHUNK, (n + 1) * CHUNK));
    onProgress(Math.round(((n + 1) / total) * 100));
  }
  return (await axios.post(`${API}/uploads/${upload_id}/complete`, { name, scale_hint: scaleHint })).data;
}

export async function streamChat(id, message, pageIndex, scope, { onDelta, onStatus, onSources }) {
  const res = await fetch(`${API}/projects/${id}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, page_index: pageIndex, scope }),
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
      if (ev.status) onStatus?.(ev.status);
      if (ev.sources) onSources?.(ev.sources);
      if (ev.delta) onDelta(ev.delta);
    }
  }
}
