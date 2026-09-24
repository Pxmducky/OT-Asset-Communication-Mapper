import axios from "axios";

// Si el backend corre en otra máquina define VITE_API_URL en frontend/.env
// Ejemplo: VITE_API_URL=http://192.168.1.50:8000/api
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api",
});

export function getErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc?.at(-1) ?? ""}: ${item.msg}`).join(" · ");
  }
  if (typeof detail === "string") return detail;
  if (error?.code === "ERR_NETWORK") return "No hay conexión con el servidor.";
  return error?.message ?? "Error desconocido.";
}

export const graphApi = {
  get: async () => (await api.get("/graph")).data,
};

export const assetApi = {
  getAll: async () => (await api.get("/assets")).data,
  getById: async (id) => (await api.get(`/assets/${id}`)).data,
  getCommunications: async (id) => (await api.get(`/assets/${id}/communications`)).data,
  create: async (asset) => (await api.post("/assets", asset)).data,
  update: async (id, asset) => (await api.put(`/assets/${id}`, asset)).data,
  delete: async (id) => {
    await api.delete(`/assets/${id}`);
  },
};

export const communicationApi = {
  getAll: async () => (await api.get("/communications")).data,
  getById: async (id) => (await api.get(`/communications/${id}`)).data,
  create: async (communication) => (await api.post("/communications", communication)).data,
  update: async (id, communication) => (await api.put(`/communications/${id}`, communication)).data,
  delete: async (id) => {
    await api.delete(`/communications/${id}`);
  },
};

export const excelApi = {
  importFile: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return (await api.post("/excel/import", formData)).data;
  },

  exportFile: async () => {
    const response = await api.get("/excel/export", { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
    link.href = url;
    link.download = `ot_inventory_${stamp}.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  },
};

export default api;