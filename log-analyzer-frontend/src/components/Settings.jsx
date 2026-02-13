import React, { useState, useEffect } from "react";
import { authAPI } from "../services/api";
import Navbar from "./Navbar";
import { Save, AlertCircle, CheckCircle } from "lucide-react";

function Settings() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [project, setProject] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    password: "",
    log_source_url: "",
    user_email: "",
    discord_webhook_escalate: "",
    discord_webhook_dev: "",
  });

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const response = await authAPI.getMe();
        const projectData = response.data;
        setProject(projectData);
        setFormData({
          name: projectData.name,
          password: "",
          log_source_url: projectData.log_source_url,
          user_email: projectData.user_email,
          discord_webhook_escalate: projectData.discord_webhook_escalate,
          discord_webhook_dev: projectData.discord_webhook_dev,
        });
      } catch (err) {
        console.error("Failed to fetch project:", err);
      }
    };
    fetchProject();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess(false);
    setLoading(true);

    try {
      await authAPI.updateSettings(formData);
      setSuccess(true);

      // Update local storage
      const updatedProject = { ...project, ...formData };
      localStorage.setItem("project", JSON.stringify(updatedProject));

      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail?.errors) {
        setError(detail.errors.map((e) => e.message).join(", "));
      } else if (typeof detail === "string") {
        setError(detail);
      } else {
        setError("Failed to update settings. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (!project) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-7xl mx-auto px-4 py-8">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            Project Settings
          </h1>
          <p className="text-gray-600">Manage your project configuration</p>
        </div>

        {success && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start">
            <CheckCircle
              className="text-green-500 mr-3 flex-shrink-0"
              size={20}
            />
            <p className="text-green-700 text-sm">
              Settings updated successfully!
            </p>
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
            <AlertCircle
              className="text-red-500 mr-3 flex-shrink-0"
              size={20}
            />
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg shadow p-8 space-y-6"
        >
          {/* Project Name (Read-only) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Project Name
            </label>
            <input
              type="text"
              value={formData.name}
              disabled
              className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-100 cursor-not-allowed"
            />
            <p className="text-xs text-gray-500 mt-1">
              Project name cannot be changed
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              API Key (for log ingestion)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={project.api_key}
                disabled
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg bg-gray-100 font-mono text-sm"
              />
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(project.api_key);
                  alert("API key copied to clipboard!");
                }}
                className="px-4 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Copy
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Use this in your log shipper's X-API-Key header
            </p>
          </div>
          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              New Password (leave blank to keep current)
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="••••••••"
              minLength={8}
            />
          </div>
          {/* Log Source URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Log Source URL
            </label>
            <input
              type="url"
              name="log_source_url"
              value={formData.log_source_url}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>
          {/* User Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Your Email
            </label>
            <input
              type="email"
              name="user_email"
              value={formData.user_email}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>
          {/* Discord Webhook - ESCALATE */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Discord Webhook - Critical Incidents
            </label>
            <input
              type="url"
              name="discord_webhook_escalate"
              value={formData.discord_webhook_escalate}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>
          {/* Discord Webhook - DEV */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Discord Webhook - Dev Team
            </label>
            <input
              type="url"
              name="discord_webhook_dev"
              value={formData.discord_webhook_dev}
              onChange={handleChange}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className={`w-full py-3 rounded-lg font-semibold text-white transition-colors flex items-center justify-center ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-700"
            }`}
          >
            <Save size={18} className="mr-2" />
            {loading ? "Saving..." : "Save Settings"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Settings;
