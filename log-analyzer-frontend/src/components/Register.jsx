import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authAPI } from "../services/api";
import { AlertCircle, Activity, ArrowRight } from "lucide-react";

function Register() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [formData, setFormData] = useState({ name: "", password: "" });

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
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
      navigate("/settings"); // send straight to Settings to complete setup
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (detail?.errors) {
        setError(detail.errors.map((e) => e.message).join(", "));
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center mb-8">
          <Activity className="text-sky-500 mr-2" size={28} />
          <span className="text-xl font-semibold text-white">Log Anomaly</span>
        </div>

        <div className="rounded-2xl border border-white/10 shadow-2xl p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-white mb-1">
              Create Project
            </h1>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start">
              <AlertCircle className="text-red-400 mr-3 shrink-0" size={18} />
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Project Name
              </label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-600 text-sm"
                placeholder="my-project"
                required
                minLength={3}
                maxLength={50}
              />
              <p className="text-xs text-gray-600 mt-1">
                Letters, numbers, hyphens, underscores only
              </p>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Password
              </label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                className="w-full px-4 py-3 bg-transparent text-gray-100 border border-white/20 rounded-lg focus:ring-2 focus:ring-sky-500 focus:border-sky-500 placeholder:text-gray-600 text-sm"
                placeholder="••••••••"
                required
                minLength={8}
                autoComplete="new-password"
              />
              <p className="text-xs text-gray-600 mt-1">Minimum 8 characters</p>
            </div>

            <button
              type="submit"
              disabled={loading || !formData.name || !formData.password}
              className="w-full py-3 rounded-lg text-sm font-medium text-white transition-colors flex items-center justify-center gap-2 bg-sky-500 hover:bg-sky-600 disabled:bg-gray-600 disabled:cursor-not-allowed"
            >
              {loading ? (
                "Creating..."
              ) : (
                <>
                  <span>Create Project</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have a project?{" "}
            <Link
              to="/login"
              className="text-sky-400 hover:text-sky-300 font-medium"
            >
              Login here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Register;
