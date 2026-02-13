import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { logout } from "../services/api";
import { LogOut, Settings, Activity } from "lucide-react";

function Navbar() {
  const navigate = useNavigate();
  const project = JSON.parse(localStorage.getItem("project") || "{}");

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav className="bg-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Activity className="text-indigo-600 mr-2" size={28} />
            <span className="text-xl font-bold text-gray-800">
              Log Analyzer
            </span>
            <span className="ml-4 px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-medium">
              {project.name}
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <Link
              to="/dashboard"
              className="text-gray-700 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium transition-colors"
            >
              Dashboard
            </Link>
            <Link
              to="/settings"
              className="text-gray-700 hover:text-indigo-600 px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center"
            >
              <Settings size={18} className="mr-1" />
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="text-gray-700 hover:text-red-600 px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center"
            >
              <LogOut size={18} className="mr-1" />
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
