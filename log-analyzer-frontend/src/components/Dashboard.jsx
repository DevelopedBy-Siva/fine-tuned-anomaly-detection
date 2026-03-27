import { useState, useEffect, useCallback } from "react";
import { incidentsAPI, logServerAPI, authAPI } from "../services/api";
import Navbar from "./Navbar";
import IncidentCard from "./IncidentCard";
import {
  RefreshCw,
  AlertTriangle,
  Play,
  Square,
  AlertCircle,
} from "lucide-react";

function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const h = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(h);
  }, [value, delay]);
  return debounced;
}

function Dashboard() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isTest, setIsTest] = useState(false);
  const [logStatus, setLogStatus] = useState("unknown");
  const [logServerError, setLogServerError] = useState("");
  const [filters, setFilters] = useState({
    status: "open",
    severity: "",
    ticket_title: "",
  });

  const debouncedFilters = useDebounce(filters, 500);

  useEffect(() => {
    authAPI
      .getMe()
      .then((res) => setIsTest(res.data?.is_test ?? false))
      .catch(() => {});
  }, []);

  const fetchIncidents = useCallback(async (f) => {
    try {
      const res = await incidentsAPI.list(f);
      setIncidents(res.data);
    } catch (e) {
      console.error("fetch incidents:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchIncidents(debouncedFilters);
  }, [debouncedFilters, fetchIncidents]);
  useEffect(() => {
    const t = setInterval(() => fetchIncidents(debouncedFilters), 5000);
    return () => clearInterval(t);
  }, [debouncedFilters, fetchIncidents]);

  useEffect(() => {
    if (!isTest) return;
    let alive = true;
    const poll = async () => {
      try {
        const res = await logServerAPI.status();
        if (alive) setLogStatus(res.data?.status || "unknown");
      } catch {
        if (alive) setLogStatus("unknown");
      }
    };
    poll();
    const t = setInterval(poll, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [isTest]);

  const handleStart = async () => {
    setLogServerError("");
    setLogStatus("unknown");
    try {
      await logServerAPI.start();
      setLogStatus("running");
    } catch (err) {
      setLogServerError(
        err.response?.data?.detail || "Failed to start log server.",
      );
      setLogStatus("idle");
    }
  };

  const handleStop = async () => {
    setLogServerError("");
    setLogStatus("unknown");
    try {
      await logServerAPI.stop();
      setLogStatus("idle");
    } catch {
      setLogServerError("Failed to stop log server.");
    }
  };

  const handleClose = async (id) => {
    await incidentsAPI.close(id);
    fetchIncidents(debouncedFilters);
  };
  const handleIgnore = async (id) => {
    await incidentsAPI.ignore(id);
    fetchIncidents(debouncedFilters);
  };

  const stats = {
    total: incidents.length,
    totalEvents: incidents.reduce((s, i) => s + i.count, 0),
    highFreq: incidents.filter((i) => i.count >= 5).length,
    analyzed: incidents.filter((i) => i.analysis).length,
  };

  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-16">
        <h1 className="text-3xl font-medium text-white mb-8">
          Incident Dashboard
        </h1>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {[
            { label: "Active Incidents", value: stats.total },
            { label: "Total Events", value: stats.totalEvents },
            { label: "High Frequency", value: stats.highFreq },
            { label: "Analyzed", value: stats.analyzed },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-lg border border-gray-800 py-6 px-5"
            >
              <div className="text-3xl font-semibold text-white">{value}</div>
              <div className="text-xs text-gray-500 mt-1">{label}</div>
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-gray-800 p-5 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">
                Status
              </label>
              <select
                value={filters.status}
                onChange={(e) =>
                  setFilters({ ...filters, status: e.target.value })
                }
                className="text-sm bg-transparent w-full px-3 py-2 border border-gray-700 rounded-lg text-gray-400 focus:ring-1 focus:ring-sky-500"
              >
                <option value="" className="bg-black">
                  All
                </option>
                <option value="open" className="bg-black">
                  Open
                </option>
                <option value="closed" className="bg-black">
                  Closed
                </option>
                <option value="ignored" className="bg-black">
                  Ignored
                </option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">
                Severity
              </label>
              <select
                value={filters.severity}
                onChange={(e) =>
                  setFilters({ ...filters, severity: e.target.value })
                }
                className="text-sm bg-transparent w-full px-3 py-2 border border-gray-700 rounded-lg text-gray-400 focus:ring-1 focus:ring-sky-500"
              >
                <option value="" className="bg-black">
                  All
                </option>
                <option value="critical" className="bg-black">
                  Critical
                </option>
                <option value="high" className="bg-black">
                  High
                </option>
                <option value="medium" className="bg-black">
                  Medium
                </option>
                <option value="low" className="bg-black">
                  Low
                </option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">
                Search
              </label>
              <input
                type="text"
                value={filters.ticket_title}
                onChange={(e) =>
                  setFilters({ ...filters, ticket_title: e.target.value })
                }
                placeholder="Ticket title..."
                className="text-sm bg-transparent w-full px-3 py-2 border border-gray-700 rounded-lg text-gray-400 placeholder:text-gray-600 focus:ring-1 focus:ring-sky-500"
              />
            </div>

            {isTest && (
              <div className="flex items-end gap-2">
                <button
                  onClick={handleStart}
                  disabled={logStatus === "unknown" || logStatus === "running"}
                  className="flex-1 px-3 py-2 text-sm bg-sky-500 text-white rounded-lg flex items-center justify-center gap-1.5 hover:bg-sky-600 disabled:bg-gray-700 disabled:cursor-not-allowed transition-colors"
                >
                  <Play size={13} /> Start
                </button>
                <button
                  onClick={handleStop}
                  disabled={logStatus === "unknown" || logStatus === "idle"}
                  className="flex-1 px-3 py-2 text-sm bg-red-500 text-white rounded-lg flex items-center justify-center gap-1.5 hover:bg-red-600 disabled:bg-gray-700 disabled:cursor-not-allowed transition-colors"
                >
                  <Square size={13} /> Stop
                </button>
              </div>
            )}
          </div>

          {isTest && logServerError && (
            <div className="flex items-start gap-3 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
              <AlertCircle className="text-red-400 shrink-0 mt-0.5" size={15} />
              <p className="text-red-300 text-xs">{logServerError}</p>
            </div>
          )}
        </div>

        {loading ? (
          <div className="text-center py-12">
            <span className="loader" />
            <p className="text-gray-500 text-sm mt-4">Loading incidents...</p>
          </div>
        ) : incidents.length === 0 ? (
          <div className="text-center py-16 rounded-lg border border-gray-800">
            <AlertTriangle className="text-gray-600 mx-auto mb-3" size={32} />
            <p className="text-gray-500 text-sm">
              {filters.status || filters.severity || filters.ticket_title
                ? "No incidents match your filters"
                : "No incidents yet — logs will appear here as they are detected"}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5">
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

        <div className="fixed bottom-0 left-0 right-0 border-t border-white/5 bg-black/80 backdrop-blur px-4 py-3 text-center text-xs text-gray-600">
          <RefreshCw size={12} className="inline mr-1.5" />
          Auto-refreshing every 5 seconds
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
