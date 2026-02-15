import React from "react";
import { AlertCircle, Clock, Hash, CheckCircle, XCircle } from "lucide-react";

function IncidentCard({ incident, analysis, onClose, onIgnore }) {
  const getSeverityColor = (count) => {
    if (count >= 10) return "bg-red-100 text-red-800 border-red-300";
    if (count >= 5) return "bg-orange-100 text-orange-800 border-orange-300";
    if (count >= 2) return "bg-yellow-100 text-yellow-800 border-yellow-300";
    return "bg-green-100 text-green-800 border-green-300";
  };

  const getSeverityLabel = (count) => {
    if (count >= 10) return "CRITICAL";
    if (count >= 5) return "HIGH";
    if (count >= 2) return "MEDIUM";
    return "LOW";
  };

  const getDispositionColor = (disposition) => {
    const colors = {
      ESCALATE: "bg-red-100 text-red-800",
      NEEDS_ONCALL: "bg-orange-100 text-orange-800",
      NEEDS_DEV: "bg-yellow-100 text-yellow-800",
      OBSERVE: "bg-blue-100 text-blue-800",
      NO_ACTION: "bg-green-100 text-green-800",
    };
    return colors[disposition] || "bg-gray-100 text-gray-800";
  };

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className="rounded-lg shadow-md hover:shadow-lg transition-shadow p-6 border border-gray-800">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center space-x-3">
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold border ${getSeverityColor(incident.count)}`}
          >
            {getSeverityLabel(incident.count)}
          </span>
          <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium">
            {incident.source}
          </span>
          <span className="px-3 py-1 bg-indigo-600 text-white rounded-full text-xs font-bold">
            {incident.count}x
          </span>
        </div>
        <div className="flex items-center text-sm text-gray-500">
          <Clock size={14} className="mr-1" />
          {formatTime(incident.last_seen)}
        </div>
      </div>

      <div className="bg-gray-900 text-gray-100 p-4 rounded-lg mb-4 overflow-x-auto">
        <code className="text-xs font-mono whitespace-pre-wrap break-all">
          {incident.sample_lines?.[0] || "N/A"}
        </code>
      </div>

      {analysis && (
        <div className="bg-gray-900 rounded-lg p-4 mb-4">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center">
              <AlertCircle
                className="text-green-600 mr-2  shrink-0"
                size={24}
              />
              <span className="text-sm font-medium text-gray-400 px-2">
                {analysis.summary}
              </span>
            </div>
            <span
              className={`px-3 py-1 whitespace-nowrap rounded text-xs font-bold ${analysis.analysis_source === "runbook" ? "bg-green-100 text-green-800" : "bg-purple-100 text-purple-800"}`}
            >
              {analysis.analysis_source === "runbook" ? "Runbook" : "✨ AI "}
            </span>
          </div>

          <div className="flex items-center space-x-2 mt-5 mb-3">
            <span
              className={`px-2 py-1 rounded text-xs font-semibold ${getDispositionColor(analysis.disposition)}`}
            >
              {analysis.disposition}
            </span>
            <span className="text-xs text-gray-400">
              Confidence: {Math.round(analysis.confidence * 100)}%
            </span>
          </div>

          {analysis.next_steps && analysis.next_steps.length > 0 && (
            <div className="mt-5 mb-5">
              <p className="text-sm font-semibold text-gray-400 mb-2">
                Next Steps:
              </p>
              <ol className="list-decimal list-inside space-y-2">
                {analysis.next_steps.slice(0, 3).map((step, idx) => (
                  <li key={idx} className="text-xs text-gray-400">
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Ticket Draft */}
          {analysis.analysis_source === "llm" && analysis.ticket_title && (
            <div className="mt-4 p-3 bg-pink-50 rounded border border-pink-200">
              <p className="text-xs font-semibold text-pink-800 mb-1">
                🎫 Ticket Draft
              </p>
              <p className="text-sm font-normal text-gray-800 mb-2">
                {analysis.ticket_title}
              </p>
              <p className="text-xs text-gray-500 line-clamp-3">
                {analysis.ticket_body}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Signature */}
      {/* <div className="flex items-center text-xs text-gray-400 mb-4">
        <Hash size={12} className="mr-1" />
        {incident.signature.substring(0, 16)}...
      </div> */}

      {/* Actions */}
      {incident.status === "open" && (
        <div className="flex space-x-2">
          <button
            onClick={() => onClose(incident.id)}
            className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium flex items-center justify-center"
          >
            <CheckCircle size={16} className="mr-1" />
            Close
          </button>
          <button
            onClick={() => onIgnore(incident.id)}
            className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm font-medium flex items-center justify-center"
          >
            <XCircle size={16} className="mr-1" />
            Ignore
          </button>
        </div>
      )}

      {incident.status !== "open" && (
        <div className="text-center py-2 px-4 bg-gray-500 rounded-lg">
          <span className="text-sm font-medium text-gray-200">
            Status: {incident.status.toUpperCase()}
          </span>
        </div>
      )}
    </div>
  );
}

export default IncidentCard;
