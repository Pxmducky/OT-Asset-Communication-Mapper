
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api",
  headers: {
    "Content-Type": "application/json",
  },
});

export const assetApi = {
  getAll: async () => {
    const response = await api.get("/assets", {
      params: {
        skip: 0,
        limit: 1000,
      },
    });

    return response.data;
  },

  getById: async (id) => {
    const response = await api.get(`/assets/${id}`);
    return response.data;
  },

  getCommunications: async (id) => {
    const response = await api.get(
      `/assets/${id}/communications`
    );

    return response.data;
  },

  create: async (asset) => {
    const response = await api.post(
      "/assets",
      asset
    );

    return response.data;
  },

  update: async (id, asset) => {
    const response = await api.put(
      `/assets/${id}`,
      asset
    );

    return response.data;
  },

  delete: async (id) => {
    await api.delete(`/assets/${id}`);
  },
};


export const communicationApi = {
  getAll: async () => {
    const response = await api.get(
      "/communications",
      {
        params: {
          skip: 0,
          limit: 1000,
        },
      }
    );

    return response.data;
  },

  getById: async (id) => {
    const response = await api.get(
      `/communications/${id}`
    );

    return response.data;
  },

  create: async (communication) => {
    const response = await api.post(
      "/communications",
      communication
    );

    return response.data;
  },

  update: async (id, communication) => {
    const response = await api.put(
      `/communications/${id}`,
      communication
    );

    return response.data;
  },

  delete: async (id) => {
    await api.delete(
      `/communications/${id}`
    );
  },
};


export default api;
