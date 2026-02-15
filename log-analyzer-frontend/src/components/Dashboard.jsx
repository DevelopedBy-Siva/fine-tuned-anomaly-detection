import React, { useState, useEffect } from "react";
import { incidentsAPI } from "../services/api";
import Navbar from "./Navbar";
import IncidentCard from "./IncidentCard";
import { RefreshCw, Filter, AlertTriangle } from "lucide-react";

function Dashboard() {
  const [incidents, setIncidents] = useState([]);
  //   const [analyses, setAnalyses] = useState({});
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
    <div className="min-h-screen">
      <Navbar />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-16">
        <div className="mb-8">
          <h1 className="text-3xl font-medium text-white mb-2">
            Incident Dashboard
          </h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 my-10">
          <div className="box-bg-color rounded-lg border border-gray-800 shadow-md shadow-gray-900 py-8 px-6 min-h-[120px]">
            <div className="text-4xl font-medium text-black">{stats.total}</div>
            <div className="text-sm text-gray-600 mt-2">Active Incidents</div>
          </div>

          <div className="box-bg-color rounded-lg border border-gray-800 shadow-md shadow-gray-900 py-8 px-6 min-h-[120px]">
            <div className="text-4xl font-medium text-black">
              {incidents.reduce((sum, i) => sum + i.count, 0)}
            </div>
            <div className="text-sm text-gray-600 mt-2">Total Events</div>
          </div>

          <div className="box-bg-color rounded-lg border border-gray-800 shadow-md shadow-gray-900 py-8 px-6 min-h-[120px]">
            <div className="text-4xl font-medium text-black">
              {stats.highFrequency}
            </div>
            <div className="text-sm text-gray-600 mt-2">High Frequency</div>
          </div>

          <div className="box-bg-color rounded-lg border border-gray-800 shadow-md shadow-gray-900 py-8 px-6 min-h-[120px]">
            <div className="text-4xl font-medium text-black">
              {stats.analyzed}
            </div>
            <div className="text-sm text-gray-600 mt-2">Analyzed</div>
          </div>
        </div>
        {/* Filters */}
        <div className="box-bg rounded-lg shadow p-6 mb-8">
          {/* <div className="flex items-center mb-4">
            <Filter size={16} className="text-gray-600 mr-2" />
            <h2 className="text-lg font-medium text-gray-500">Filters</h2>
          </div> */}
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
                className={`text-sm bg-transparent w-full px-4 py-2 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 text-gray-500`}
              >
                <option value="" className="bg-black text-gray-400">
                  All
                </option>
                <option value="open" className="bg-black text-gray-400">
                  Open
                </option>
                <option value="closed" className="bg-black text-gray-400">
                  Closed
                </option>
                <option value="ignored" className="bg-black text-gray-400">
                  Ignored
                </option>
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
                className="text-sm bg-transparent w-full px-4 py-2 border border-white/10 rounded-lg focus:ring-2 focus:ring-indigo-500 text-gray-500  placeholder:text-gray-500"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={fetchIncidents}
                className="text-sm w-full px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 transition-colors flex items-center justify-center"
              >
                <RefreshCw size={14} className="mr-2" />
                Refresh
              </button>
            </div>
          </div>
        </div>
        {/* Incidents List */}
        {loading ? (
          <div className="text-center py-12">
            <span className="loader"></span>
            <p className="text-gray-600 py-4 text-sm">Loading incidents...</p>
          </div>
        ) : incidents.length === 0 ? (
          <div className="box-bg text-center py-12  rounded-lg shadow">
            <AlertTriangle className="text-gray-600 mx-auto mb-2" size={38} />
            <h3 className="text-xl font-semibold text-gray-800 mb-1">
              No incidents found
            </h3>
            <p className="text-gray-700 text-sm">
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
                analysis={incident.analysis}
                onClose={handleClose}
                onIgnore={handleIgnore}
              />
            ))}
          </div>
        )}
        <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/10 bg-black/70 backdrop-blur px-4 py-4 text-center text-xs text-gray-600">
          <RefreshCw size={14} className="inline mr-2" />
          Auto-refreshing every 5 seconds
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
