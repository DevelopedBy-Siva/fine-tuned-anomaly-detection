import axios from "axios";

export const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:8000";
export const TEST_LOG_SERVER_URL =
  process.env.REACT_APP_TEST_LOG_SERVER_URL || "http://localhost:8001";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const authAPI = {
  register: (data) => api.post("/api/auth/register", data),
  login: (data) => api.post("/api/auth/login", data),
  getMe: () => api.get("/api/auth/me"),
  updateSettings: (data) => api.put("/api/auth/settings", data),
  settingsStatus: () => api.get("/api/auth/settings/status"),
};

export const logServerAPI = {
  start: () => api.post("/api/log-server/start"),
  stop: () => api.post("/api/log-server/stop"),
  status: () => api.get("/api/log-server/status"),
  runScenario: (name) => api.post(`/api/log-server/scenario/${name}`),
  listScenarios: () => api.get("/api/log-server/scenarios"),
};

export const incidentsAPI = {
  list: (params) => api.get("/api/incidents", { params }),
  get: (id) => api.get(`/api/incidents/${id}`),
  close: (id) => api.post(`/api/incidents/${id}/close`),
  ignore: (id) => api.post(`/api/incidents/${id}/ignore`),
  // Agent visibility — new
  getEvidence: (id) => api.get(`/api/incidents/${id}/evidence`),
  getActions: (id) => api.get(`/api/incidents/${id}/actions`),
  getInvestigation: (id) => api.get(`/api/incidents/${id}/investigation`),
};

export const isAuthenticated = () => !!localStorage.getItem("token");

export const logout = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("project");
  window.location.href = "/login";
};

export default api;
