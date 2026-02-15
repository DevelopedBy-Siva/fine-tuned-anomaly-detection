import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { logout } from "../services/api";
import { LogOut, Settings, Activity, Home } from "lucide-react";

function Navbar() {
  const navigate = useNavigate();
  const project = JSON.parse(localStorage.getItem("project") || "{}");

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav className="box-bg border-b border-gray-800 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          <div className="flex items-center">
            <Activity className="text-sky-500 mr-2" size={28} />
          </div>

          <div className="flex items-center space-x-4">
            <Link
              to="/dashboard"
              className="text-gray-500 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center"
            >
              <Home size={16} className="mr-1" /> Dashboard
            </Link>
            <Link
              to="/settings"
              className="text-gray-500 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center"
            >
              <Settings size={16} className="mr-1" />
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="text-gray-500 hover:text-red-600 px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center"
            >
              <LogOut size={16} className="mr-1" />
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
