import React, { useState, useEffect } from "react";
import { incidentsAPI } from "../services/api";
import Navbar from "./Navbar";
import IncidentCard from "./IncidentCard";
import { RefreshCw, Filter, AlertTriangle } from "lucide-react";

function Dashboard() {
  const [incidents, setIncidents] = useState([]);
  const [analyses, setAnalyses] = useState({});
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: "open",
    source: "",
  });

  // Replace the fetchIncidents function with this:
  const fetchIncidents = async () => {
    try {
      const response = await incidentsAPI.list(filters);
      const incidentsList = response.data;
      setIncidents(incidentsList);
    } catch (err) {
      console.error("Failed to fetch incidents:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, [filters]);

  const handleClose = async (id) => {
    try {
      await incidentsAPI.close(id);
      fetchIncidents();
    } catch (err) {
      console.error("Failed to close incident:", err);
    }
  };

  const handleIgnore = async (id) => {
    try {
      await incidentsAPI.ignore(id);
      fetchIncidents();
    } catch (err) {
      console.error("Failed to ignore incident:", err);
    }
  };

  const stats = {
    total: incidents.length,
    highFrequency: incidents.filter((i) => i.count >= 5).length,
    analyzed: incidents.filter((i) => i.analysis).length, // Changed
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            Incident Dashboard
          </h1>
          <p className="text-gray-600">
            Real-time monitoring and AI-powered analysis
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-indigo-500">
            <div className="text-3xl font-bold text-gray-800">
              {stats.total}
            </div>
            <div className="text-sm text-gray-600 mt-1">Active Incidents</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-orange-500">
            <div className="text-3xl font-bold text-gray-800">
              {incidents.reduce((sum, i) => sum + i.count, 0)}
            </div>
            <div className="text-sm text-gray-600 mt-1">Total Events</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-red-500">
            <div className="text-3xl font-bold text-gray-800">
              {stats.highFrequency}
            </div>
            <div className="text-sm text-gray-600 mt-1">High Frequency</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-500">
            <div className="text-3xl font-bold text-gray-800">
              {stats.analyzed}
            </div>
            <div className="text-sm text-gray-600 mt-1">Analyzed</div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="flex items-center mb-4">
            <Filter size={20} className="text-gray-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-800">Filters</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Status
              </label>
              <select
                value={filters.status}
                onChange={(e) =>
                  setFilters({ ...filters, status: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">All</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
                <option value="ignored">Ignored</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Source
              </label>
              <input
                type="text"
                value={filters.source}
                onChange={(e) =>
                  setFilters({ ...filters, source: e.target.value })
                }
                placeholder="Filter by source..."
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={fetchIncidents}
                className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors flex items-center justify-center"
              >
                <RefreshCw size={18} className="mr-2" />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Incidents List */}
        {loading ? (
          <div className="text-center py-12">
            <RefreshCw
              className="animate-spin text-indigo-600 mx-auto mb-4"
              size={48}
            />
            <p className="text-gray-600">Loading incidents...</p>
          </div>
        ) : incidents.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <AlertTriangle className="text-gray-400 mx-auto mb-4" size={48} />
            <h3 className="text-xl font-semibold text-gray-800 mb-2">
              No incidents found
            </h3>
            <p className="text-gray-600">
              {filters.status || filters.source
                ? "Try adjusting your filters"
                : "Start generating logs to see incidents here"}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {incidents.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                analysis={incident.analysis} // Changed from analyses[incident.id]
                onClose={handleClose}
                onIgnore={handleIgnore}
              />
            ))}
          </div>
        )}

        {/* Auto-refresh indicator */}
        <div className="text-center mt-8 text-sm text-gray-500">
          <RefreshCw size={14} className="inline mr-1" />
          Auto-refreshing every 5 seconds
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
