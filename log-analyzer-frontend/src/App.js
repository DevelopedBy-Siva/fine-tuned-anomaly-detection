import React, { useEffect, useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import {
  API_BASE_URL,
  isAuthenticated,
  TEST_LOG_SERVER_URL,
} from "./services/api";
import Login from "./components/Login";
import Register from "./components/Register";
import Dashboard from "./components/Dashboard";
import Settings from "./components/Settings";
import axios from "axios";
import { MdError } from "react-icons/md";

// Protected Route wrapper
function ProtectedRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" />;
}

// Public Route wrapper (redirect to dashboard if already logged in)
function PublicRoute({ children }) {
  return !isAuthenticated() ? children : <Navigate to="/dashboard" />;
}

function App() {
  const [status, setStatus] = useState({
    serverA: "pending",
    serverB: "pending",
  });

  useEffect(() => {
    const wake = async (name, url) => {
      try {
        await axios.get(url, { timeout: 15000 });
        setStatus((s) => ({ ...s, [name]: "up" }));
        return true;
      } catch {
        setStatus((s) => ({ ...s, [name]: "down" }));
        return false;
      }
    };

    const wakeAll = async () => {
      await Promise.all([
        wake("serverA", `${API_BASE_URL}/health`),
        wake("serverB", `${TEST_LOG_SERVER_URL}/health`),
      ]);
    };

    wakeAll();
  }, []);

  return status.serverA !== "up" && status.serverB !== "up" ? (
    <div className="server-loading">
      {status.serverA === "pending" || status.serverB === "pending" ? (
        <>
          <span class="loader"></span>
          <p>
            Please allow a few seconds for everything to initialize, as the
            servers are on free instances.
          </p>
        </>
      ) : status.serverA === "down" || status.serverB === "down" ? (
        <>
          <MdError />
          <p>Failed to initialize the server. Please try again later. </p>
        </>
      ) : (
        <p>Initialize Successful </p>
      )}
      <p></p>
    </div>
  ) : (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />
        <Route
          path="/register"
          element={
            <PublicRoute>
              <Register />
            </PublicRoute>
          }
        />

        {/* Protected Routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />

        {/* Default Route */}
        <Route path="/" element={<Navigate to="/dashboard" />} />

        {/* 404 */}
        <Route
          path="*"
          element={
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <div className="text-center">
                <h1 className="text-6xl font-bold text-gray-800 mb-4">404</h1>
                <p className="text-gray-600 mb-8">Page not found</p>
                <a
                  href="/dashboard"
                  className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  Go to Dashboard
                </a>
              </div>
            </div>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
