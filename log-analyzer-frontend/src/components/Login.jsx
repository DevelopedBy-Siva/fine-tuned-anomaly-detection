import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authAPI } from "../services/api";
import { AlertCircle } from "lucide-react";
import { Activity } from "lucide-react";

function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [formData, setFormData] = useState({
    name: "",
    password: "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await authAPI.login(formData);
      const { access_token, project } = response.data;

      localStorage.setItem("token", access_token);
      localStorage.setItem("project", JSON.stringify(project));

      navigate("/dashboard");
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Login failed. Please check your credentials.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 pt-20 relative">
      <div className="absolute top-6 left-6 flex items-center">
        <Activity className="text-sky-500 mr-2" size={28} />
      </div>
      <div className="rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Login</h1>
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
            />
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
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full py-3 rounded-lg text-sm font-medium text-white transition-colors ${
              loading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-sky-500 hover:bg-sky-600"
            }`}
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600 mt-6">
          Don't have a project?{" "}
          <Link
            to="/register"
            className="text-sky-500 hover:text-sky-600 font-medium"
          >
            Create one here
          </Link>
        </p>
      </div>
    </div>
  );
}

export default Login;
