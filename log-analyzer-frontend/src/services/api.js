import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth API
export const authAPI = {
  register: (data) => api.post("/api/auth/register", data),
  login: (data) => api.post("/api/auth/login", data),
  getMe: () => api.get("/api/auth/me"),
  updateSettings: (data) => api.put("/api/auth/settings", data),

  // Validation endpoints
  validateUrl: (url) => api.post("/api/auth/validate/url", { url }),
  validateDiscordEscalate: (webhook_url) =>
    api.post("/api/auth/validate/discord-escalate", { webhook_url }),
  validateDiscordDev: (webhook_url) =>
    api.post("/api/auth/validate/discord-dev", { webhook_url }),
  validateEmail: (email) => api.post("/api/auth/validate/email", { email }),
};

// Incidents API
export const incidentsAPI = {
  list: (params) => api.get("/api/incidents", { params }),
  get: (id) => api.get(`/api/incidents/${id}`),
  close: (id) => api.post(`/api/incidents/${id}/close`),
  ignore: (id) => api.post(`/api/incidents/${id}/ignore`),
};

// Helper to check if user is authenticated
export const isAuthenticated = () => {
  return !!localStorage.getItem("token");
};

// Helper to logout
export const logout = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("project");
  window.location.href = "/login";
};

export default api;
