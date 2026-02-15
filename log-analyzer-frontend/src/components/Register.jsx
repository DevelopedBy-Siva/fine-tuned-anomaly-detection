import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authAPI } from "../services/api";
import {
  CheckCircle,
  XCircle,
  Loader,
  AlertCircle,
  Activity,
} from "lucide-react";

function Register() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [formData, setFormData] = useState({
    name: "",
    password: "",
    log_source_url: "",
    user_email: "",
    discord_webhook_escalate: "",
    discord_webhook_dev: "",
  });

  const [validation, setValidation] = useState({
    log_source_url: { status: null, message: "" },
    user_email: { status: null, message: "" },
    discord_webhook_escalate: { status: null, message: "" },
    discord_webhook_dev: { status: null, message: "" },
  });

  const [validating, setValidating] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Reset validation when user types
    if (validation[name]) {
      setValidation((prev) => ({
        ...prev,
        [name]: { status: null, message: "" },
      }));
    }
  };

  const validateField = async (field) => {
    const value = formData[field];
    if (!value) return;

    setValidating((prev) => ({ ...prev, [field]: true }));

    try {
      let response;

      switch (field) {
        case "log_source_url":
          response = await authAPI.validateUrl(value);
          break;
        case "discord_webhook_escalate":
          response = await authAPI.validateDiscordEscalate(value);
          break;
        case "discord_webhook_dev":
          response = await authAPI.validateDiscordDev(value);
          break;
        case "user_email":
          response = await authAPI.validateEmail(value);
          break;
        default:
          return;
      }

      const { is_valid, message } = response.data;
      setValidation((prev) => ({
        ...prev,
        [field]: { status: is_valid ? "success" : "error", message },
      }));
    } catch (err) {
      setValidation((prev) => ({
        ...prev,
        [field]: {
          status: "error",
          message: err.response?.data?.detail || "Validation failed",
        },
      }));
    } finally {
      setValidating((prev) => ({ ...prev, [field]: false }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await authAPI.register(formData);
      const { access_token, project } = response.data;

      localStorage.setItem("token", access_token);
      localStorage.setItem("project", JSON.stringify(project));

      navigate("/dashboard");
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail?.errors) {
        setError(detail.errors.map((e) => e.message).join(", "));
      } else if (typeof detail === "string") {
        setError(detail);
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const allValid = Object.values(validation).every(
    (v) => v.status === "success",
  );

  return (
    <div className="max-w-7xl mx-auto min-h-screen flex flex-col items-center justify-center p-4 pt-20 relative">
      <div className="flex items-center">
        <Activity className="text-sky-500 mr-2" size={28} />
      </div>
      <div className="rounded-2xl shadow-2xl w-full max-w-2xl p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Create Your Project
          </h1>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
            <AlertCircle
              className="text-red-500 mr-3 flex-shrink-0"
              size={20}
            />
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-normal text-gray-400 mb-2">
              Project Name
            </label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="text-sm w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-500"
              placeholder="my-awesome-project"
              required
              minLength={3}
              maxLength={50}
              title="Only letters, numbers, hyphens, and underscores"
            />
            <p className="text-xs text-gray-500 mt-1">
              3-50 characters, alphanumeric + hyphens/underscores
            </p>
          </div>

          <div>
            <label className="block text-sm font-normal text-gray-400 mb-2">
              Password
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-500"
              placeholder="••••••••"
              required
              autoComplete="new-password"
              minLength={8}
              maxLength={72}
            />
            <p className="text-xs text-gray-500 mt-1">Minimum 8 characters</p>
          </div>

          <div>
            <label className="block text-sm font-normal text-gray-400 mb-2">
              Log Source URL
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                name="log_source_url"
                value={formData.log_source_url}
                onChange={handleChange}
                onBlur={() => validateField("log_source_url")}
                className="text-sm w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-500"
                placeholder="http://localhost:5001"
                required
              />
              {validating.log_source_url && (
                <Loader className="animate-spin text-indigo-500" size={20} />
              )}
              {validation.log_source_url.status === "success" && (
                <CheckCircle className="text-green-500" size={20} />
              )}
              {validation.log_source_url.status === "error" && (
                <XCircle className="text-red-500" size={20} />
              )}
            </div>
            {validation.log_source_url.message && (
              <p
                className={`text-xs mt-1 ${validation.log_source_url.status === "success" ? "text-green-600" : "text-red-600"}`}
              >
                {validation.log_source_url.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-normal text-gray-400 mb-2">
              Your Email
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                name="user_email"
                value={formData.user_email}
                onChange={handleChange}
                onBlur={() => validateField("user_email")}
                className="text-sm w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-500"
                placeholder="you@example.com"
                required
              />
              {validating.user_email && (
                <Loader className="animate-spin text-indigo-500" size={20} />
              )}
              {validation.user_email.status === "success" && (
                <CheckCircle className="text-green-500" size={20} />
              )}
              {validation.user_email.status === "error" && (
                <XCircle className="text-red-500" size={20} />
              )}
            </div>
            {validation.user_email.message && (
              <p
                className={`text-xs mt-1 ${validation.user_email.status === "success" ? "text-green-600" : "text-red-600"}`}
              >
                {validation.user_email.message}
              </p>
            )}
            <p className="text-xs text-gray-500 mt-1">
              Where to send incident notifications
            </p>
          </div>

          <div>
            <label className="block text-sm font-normal text-gray-400 mb-2">
              Discord Webhook - Critical Incidents
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                name="discord_webhook_escalate"
                value={formData.discord_webhook_escalate}
                onChange={handleChange}
                onBlur={() => validateField("discord_webhook_escalate")}
                className="text-sm w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-500"
                placeholder="https://discord.com/api/webhooks/..."
                required
              />
              {validating.discord_webhook_escalate && (
                <Loader className="animate-spin text-indigo-500" size={20} />
              )}
              {validation.discord_webhook_escalate.status === "success" && (
                <CheckCircle className="text-green-500" size={20} />
              )}
              {validation.discord_webhook_escalate.status === "error" && (
                <XCircle className="text-red-500" size={20} />
              )}
            </div>
            {validation.discord_webhook_escalate.message && (
              <p
                className={`text-xs mt-1 ${validation.discord_webhook_escalate.status === "success" ? "text-green-600" : "text-red-600"}`}
              >
                {validation.discord_webhook_escalate.message}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-normal text-gray-400 mb-2">
              Discord Webhook - Dev Team
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                name="discord_webhook_dev"
                value={formData.discord_webhook_dev}
                onChange={handleChange}
                onBlur={() => validateField("discord_webhook_dev")}
                className="text-sm w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-500"
                placeholder="https://discord.com/api/webhooks/..."
                required
              />
              {validating.discord_webhook_dev && (
                <Loader className="animate-spin text-indigo-500" size={20} />
              )}
              {validation.discord_webhook_dev.status === "success" && (
                <CheckCircle className="text-green-500" size={20} />
              )}
              {validation.discord_webhook_dev.status === "error" && (
                <XCircle className="text-red-500" size={20} />
              )}
            </div>
            {validation.discord_webhook_dev.message && (
              <p
                className={`text-xs mt-1 ${validation.discord_webhook_dev.status === "success" ? "text-green-600" : "text-red-600"}`}
              >
                {validation.discord_webhook_dev.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !allValid}
            className={`w-full py-3 rounded-lg text-sm font-medium text-white transition-colors ${
              loading || !allValid
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-sky-500 hover:bg-sky-600"
            }`}
          >
            {loading ? "Creating Project..." : "Create Project"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600 mt-6">
          Already have a project?{" "}
          <Link
            to="/login"
            className="text-sky-500 hover:text-sky-600 font-medium"
          >
            Login here
          </Link>
        </p>
      </div>
    </div>
  );
}

export default Register;
