import api from "./api";

export const scanProfileApi = {
  list: async () => (await api.get("/scans/profiles")).data,
};

export const scanApi = {
  list: async () => (await api.get("/scans")).data,
  request: async (payload) => (await api.post("/scans/request", payload)).data,
};

export const networkApi = {
  list: async () => (await api.get("/networks")).data,
  add: async (payload) => (await api.post("/networks", payload)).data,
  update: async (id, payload) => (await api.patch(`/networks/${id}`, payload)).data,
  remove: async (id) => {
    await api.delete(`/networks/${id}`);
  },
};


export const findingApi = {
  list: async (status) =>
    (await api.get("/findings", { params: status ? { status } : {} })).data,
  forScan: async (scanId) => (await api.get(`/scans/${scanId}/findings`)).data,
  apply: async (id) => (await api.post(`/findings/${id}/apply`)).data,
  discard: async (id) => (await api.post(`/findings/${id}/discard`)).data,
};

export const assetServiceApi = {
  list: async (assetId) => (await api.get(`/assets/${assetId}/services`)).data,
};

export const backupApi = {
  list: async () => (await api.get("/backups")).data,
  create: async () => (await api.post("/backups")).data,
  remove: async (id) => {
    await api.delete(`/backups/${id}`);
  },
  restore: async (id) => (await api.post(`/backups/${id}/restore`)).data,
  download: async (id, filename) => {
    const response = await api.get(`/backups/${id}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || `backup_${id}.db`;
    link.click();
    URL.revokeObjectURL(url);
  },
};