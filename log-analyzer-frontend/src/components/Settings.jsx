import React, { useState, useEffect } from "react";
import { authAPI } from "../services/api";
import Navbar from "./Navbar";
import { Save, AlertCircle, CheckCircle } from "lucide-react";

function Settings() {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [project, setProject] = useState(null);
  const [isTest, setIsTest] = useState(false);

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
        setIsTest(projectData.is_test);
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
      <div className="min-h-screen flex flex-col">
        <Navbar />

        <div className="flex-1 flex items-center justify-center">
          <span className="loader"></span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Navbar />

      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-medium text-white mb-2">
            Project Settings
          </h1>
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
          className="rounded-lg shadow p-8 space-y-7"
        >
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Project Name
            </label>
            <input
              type="text"
              value={formData.name}
              disabled
              className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg bg-gray-100 cursor-not-allowed"
            />
            <p className="py-1 text-xs text-gray-700 mt-1">
              Project name cannot be changed
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              API Key (for log ingestion)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={project.api_key}
                disabled
                className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg bg-gray-100 cursor-not-allowed"
              />
              <button
                type="button"
                disabled={isTest}
                onClick={() => {
                  navigator.clipboard.writeText(project.api_key);
                  alert("API key copied to clipboard!");
                }}
                className="text-xs px-4 py-3 bg-sky-500 text-white rounded-lg hover:bg-sky-600"
              >
                Copy
              </button>
            </div>
            <p className="py-1 text-xs text-gray-700 mt-1">
              Use this in your log shipper's X-API-Key header
            </p>
          </div>
          {/* Password */}
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              New Password (leave blank to keep current)
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg  disabled:bg-transparent disabled:text-gray-500"
              placeholder="••••••••"
              minLength={8}
              disabled={isTest}
              autoComplete="new-password"
            />
          </div>
          {/* Log Source URL */}
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Log Source URL
            </label>
            <input
              type="url"
              name="log_source_url"
              value={formData.log_source_url}
              onChange={handleChange}
              className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg bg-gray-100 "
              required
              disabled={isTest}
            />
          </div>
          {/* User Email */}
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Your Email
            </label>
            <input
              type="email"
              name="user_email"
              value={formData.user_email}
              onChange={handleChange}
              className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg bg-gray-100 "
              required
              disabled={isTest}
            />
          </div>
          {/* Discord Webhook - ESCALATE */}
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Discord Webhook - Critical Incidents
            </label>
            <input
              type="url"
              name="discord_webhook_escalate"
              value={formData.discord_webhook_escalate}
              onChange={handleChange}
              className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg bg-gray-100 "
              required
              disabled={isTest}
            />
          </div>
          {/* Discord Webhook - DEV */}
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-2">
              Discord Webhook - Dev Team
            </label>
            <input
              type="url"
              name="discord_webhook_dev"
              value={formData.discord_webhook_dev}
              onChange={handleChange}
              className="bg-transparent text-sm text-gray-100 w-full px-4 py-3 border border-gray-800 rounded-lg "
              required
              disabled={isTest}
            />
          </div>
          <button
            type="submit"
            disabled={isTest || loading}
            className={`text-sm font-normal w-full py-3 rounded-lg font-semibold text-white transition-colors flex items-center justify-center  ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-sky-500 hover:bg-sky-600"
            }`}
          >
            <Save size={16} className="mr-2" />
            {loading ? "Saving..." : "Save Settings"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Settings;
