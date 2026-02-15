import axios from "axios";

export const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:8000";
export const TEST_LOG_SERVER_URL =
  process.env.REACT_APP_TEST_LOG_SERVER_URL || "http://localhost:5001";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authAPI = {
  register: (data) => api.post("/api/auth/register", data),
  login: (data) => api.post("/api/auth/login", data),
  getMe: () => api.get("/api/auth/me"),
  updateSettings: (data) => api.put("/api/auth/settings", data),
  startLogServer: () => api.post("/api/auth/log-server/start"),
  stopLogServer: () => api.post("/api/auth/log-server/stop"),
  statusLogServer: () => api.get("/api/auth/log-server/status"),

  validateUrl: (url) => api.post("/api/auth/validate/url", { url }),
  validateDiscordEscalate: (webhook_url) =>
    api.post("/api/auth/validate/discord-escalate", { webhook_url }),
  validateDiscordDev: (webhook_url) =>
    api.post("/api/auth/validate/discord-dev", { webhook_url }),
  validateEmail: (email) => api.post("/api/auth/validate/email", { email }),
};

export const incidentsAPI = {
  list: (params) => api.get("/api/incidents", { params }),
  get: (id) => api.get(`/api/incidents/${id}`),
  close: (id) => api.post(`/api/incidents/${id}/close`),
  ignore: (id) => api.post(`/api/incidents/${id}/ignore`),
};

export const isAuthenticated = () => {
  return !!localStorage.getItem("token");
};

export const logout = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("project");
  window.location.href = "/login";
};

export default api;
