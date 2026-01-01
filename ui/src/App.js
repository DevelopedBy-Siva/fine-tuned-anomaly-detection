import { useState, useRef } from "react";

const Header = () => {
  return (
    <header style={styles.header}>
      <div style={styles.headerContent}>
        <div style={styles.logo}>
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="#4F46E5" />
            <path
              d="M8 12h16M8 16h16M8 20h10"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <h1 style={styles.title}>Log Anomaly Detector</h1>
        </div>
      </div>
    </header>
  );
};

const FileUpload = ({ onFileSelect, isAnalyzing }) => {
  const fileInputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    if (file.name.endsWith(".log") || file.name.endsWith(".txt")) {
      setFileName(file.name);
      onFileSelect(file);
    } else {
      alert("Please upload a .log or .txt file");
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current.click();
  };

  return (
    <div style={styles.uploadSection}>
      <div
        style={{
          ...styles.dropZone,
          ...(dragActive ? styles.dropZoneActive : {}),
          ...(isAnalyzing ? styles.dropZoneDisabled : {}),
        }}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleButtonClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".log,.txt"
          onChange={handleChange}
          style={{ display: "none" }}
          disabled={isAnalyzing}
        />

        <svg
          width="64"
          height="64"
          viewBox="0 0 64 64"
          fill="none"
          style={styles.uploadIcon}
        >
          <circle
            cx="32"
            cy="32"
            r="30"
            stroke="#4F46E5"
            strokeWidth="2"
            strokeDasharray="4 4"
          />
          <path
            d="M32 20v24M20 32h24"
            stroke="#4F46E5"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>

        <h3 style={styles.uploadTitle}>
          {fileName ? fileName : "Drop your log file here"}
        </h3>
        <p style={styles.uploadSubtitle}>upload .log or .txt files only</p>

        {isAnalyzing && (
          <div style={styles.analyzing}>
            <div style={styles.spinner}></div>
            <span>Analyzing...</span>
          </div>
        )}
      </div>
    </div>
  );
};

const StatsCards = ({ results }) => {
  if (!results) return null;

  const cards = [
    {
      label: "Total Sequences",
      value: results.total_sequences.toLocaleString(),
      color: "#4F46E5",
      icon: "📊",
    },
    {
      label: "Anomalies Detected",
      value: results.anomalies_detected,
      color: results.anomalies_detected > 0 ? "#DC2626" : "#10B981",
      icon: results.anomalies_detected > 0 ? "⚠️" : "✓",
    },
    {
      label: "Anomaly Rate",
      value: `${(results.anomaly_rate * 100).toFixed(2)}%`,
      color:
        results.anomaly_rate > 0.1
          ? "#DC2626"
          : results.anomaly_rate > 0.05
          ? "#F59E0B"
          : "#10B981",
      icon: "📈",
    },
    {
      label: "Processing Time",
      value: `${results.processing_time.toFixed(2)}s`,
      color: "#8B5CF6",
      icon: "⚡",
    },
  ];

  return (
    <div style={styles.statsGrid}>
      {cards.map((card, index) => (
        <div key={index} style={styles.statCard}>
          <div style={styles.statCardHeader}>
            <span style={styles.statIcon}>{card.icon}</span>
            <span style={styles.statLabel}>{card.label}</span>
          </div>
          <div style={{ ...styles.statValue, color: card.color }}>
            {card.value}
          </div>
        </div>
      ))}
    </div>
  );
};

const Summary = ({ summary, anomalyRate }) => {
  if (!summary) return null;

  const getSeverityColor = () => {
    if (anomalyRate > 0.1) return "#DC2626";
    if (anomalyRate > 0.05) return "#F59E0B";
    return "#10B981";
  };

  return (
    <div style={{ ...styles.summaryCard, borderLeftColor: getSeverityColor() }}>
      <h3 style={styles.summaryTitle}>Analysis Summary</h3>
      <p style={styles.summaryText}>{summary}</p>
    </div>
  );
};

const AnomalyList = ({ anomalies }) => {
  if (!anomalies || anomalies.length === 0) {
    return (
      <div style={styles.noAnomalies}>
        <span style={styles.checkIcon}>✓</span>
        <h3>No Anomalies Detected</h3>
        <p>All log sequences appear normal</p>
      </div>
    );
  }

  return (
    <div style={styles.anomalySection}>
      <h3 style={styles.sectionTitle}>
        Detected Anomalies ({anomalies.length})
      </h3>

      <div style={styles.anomalyList}>
        {anomalies.map((anomaly, index) => (
          <AnomalyCard key={index} anomaly={anomaly} index={index} />
        ))}
      </div>
    </div>
  );
};

const AnomalyCard = ({ anomaly, index }) => {
  const [expanded, setExpanded] = useState(false);

  const getSeverityStyle = (severity) => {
    const styles = {
      high: { bg: "#FEE2E2", color: "#991B1B", border: "#DC2626" },
      medium: { bg: "#FEF3C7", color: "#92400E", border: "#F59E0B" },
      low: { bg: "#DBEAFE", color: "#1E40AF", border: "#3B82F6" },
    };
    return styles[severity] || styles.low;
  };

  const severityStyle = getSeverityStyle(anomaly.severity);

  return (
    <div style={styles.anomalyCard}>
      <div style={styles.anomalyHeader}>
        <div style={styles.anomalyHeaderLeft}>
          <span style={styles.anomalyNumber}>#{index + 1}</span>
          <span
            style={{
              ...styles.severityBadge,
              backgroundColor: severityStyle.bg,
              color: severityStyle.color,
              borderColor: severityStyle.border,
            }}
          >
            {anomaly.severity.toUpperCase()}
          </span>
          <span style={styles.confidence}>
            {(anomaly.confidence * 100).toFixed(1)}% confidence
          </span>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          style={styles.expandButton}
        >
          {expanded ? "−" : "+"}
        </button>
      </div>

      <div style={styles.anomalyContent}>
        <div style={styles.explanation}>
          <strong>Explanation:</strong> {anomaly.explanation}
        </div>

        {expanded && (
          <div style={styles.logSnippet}>
            <div style={styles.snippetHeader}>Log Snippet:</div>
            <pre style={styles.snippetCode}>{anomaly.log_snippet}</pre>
          </div>
        )}
      </div>
    </div>
  );
};

const App = () => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleFileSelect = async (file) => {
    setIsAnalyzing(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://44.204.148.194:8000/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Analysis failed");
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message);
      console.error("Error:", err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div style={styles.container}>
      <Header />

      <main style={styles.main}>
        <div style={styles.content}>
          <FileUpload
            onFileSelect={handleFileSelect}
            isAnalyzing={isAnalyzing}
          />

          {error && (
            <div style={styles.errorCard}>
              <span style={styles.errorIcon}>✕</span>
              <div>
                <h3 style={styles.errorTitle}>Analysis Failed</h3>
                <p style={styles.errorMessage}>{error}</p>
              </div>
            </div>
          )}

          {results && (
            <>
              <StatsCards results={results} />
              <Summary
                summary={results.summary}
                anomalyRate={results.anomaly_rate}
              />
              <AnomalyList anomalies={results.results} />
            </>
          )}
        </div>
      </main>
    </div>
  );
};

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#191919",
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },

  header: {
    backgroundColor: "#1F1F1F",
    borderBottom: "1px solid #2A2A2A",
    padding: "1.5rem 0",
    boxShadow: "0 1px 3px rgba(0,0,0,0.6)",
  },

  headerContent: {
    maxWidth: "1200px",
    margin: "0 auto",
    padding: "0 2rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },

  logo: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
  },

  title: {
    margin: 0,
    fontSize: "1.5rem",
    fontWeight: "700",
    color: "#fff",
  },

  stats: {
    display: "flex",
    gap: "1rem",
  },

  statBadge: {
    backgroundColor: "#EEF2FF",
    color: "#4F46E5",
    padding: "0.5rem 1rem",
    borderRadius: "6px",
    fontSize: "0.875rem",
    fontWeight: "600",
  },

  main: {
    maxWidth: "1200px",
    margin: "0 auto",
    padding: "2rem",
  },

  content: {
    display: "flex",
    flexDirection: "column",
    gap: "2rem",
  },

  uploadSection: {
    width: "100%",
  },

  dropZone: {
    backgroundColor: "#353535ff",
    border: "2px dashed #111827",
    borderRadius: "12px",
    padding: "3rem 2rem",
    textAlign: "center",
    cursor: "pointer",
    transition: "all 0.3s ease",
  },

  dropZoneActive: {
    borderColor: "#4F46E5",
    backgroundColor: "#EEF2FF",
  },

  dropZoneDisabled: {
    opacity: 0.6,
    cursor: "not-allowed",
  },

  uploadIcon: {
    marginBottom: "1rem",
  },

  uploadTitle: {
    margin: "0 0 0.5rem 0",
    fontSize: "1.25rem",
    fontWeight: "600",
    color: "#d6d6d6ff",
  },

  uploadSubtitle: {
    margin: 0,
    color: "#6B7280",
    fontSize: "0.875rem",
  },

  analyzing: {
    marginTop: "1.5rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.75rem",
    color: "#4F46E5",
    fontWeight: "600",
  },

  spinner: {
    width: "24px",
    height: "24px",
    border: "3px solid #EEF2FF",
    borderTop: "3px solid #4F46E5",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },

  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "1.5rem",
  },

  statCard: {
    backgroundColor: "white",
    padding: "1.5rem",
    borderRadius: "12px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },

  statCardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    marginBottom: "1rem",
  },

  statIcon: {
    fontSize: "1.5rem",
  },

  statLabel: {
    fontSize: "0.875rem",
    color: "#6B7280",
    fontWeight: "500",
  },

  statValue: {
    fontSize: "2rem",
    fontWeight: "700",
    marginTop: "0.5rem",
  },

  summaryCard: {
    backgroundColor: "white",
    padding: "1.5rem",
    borderRadius: "12px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
    borderLeft: "4px solid #10B981",
  },

  summaryTitle: {
    margin: "0 0 0.75rem 0",
    fontSize: "1.125rem",
    fontWeight: "600",
    color: "#111827",
  },

  summaryText: {
    margin: 0,
    color: "#4B5563",
    lineHeight: "1.6",
  },

  noAnomalies: {
    backgroundColor: "white",
    padding: "3rem 2rem",
    borderRadius: "12px",
    textAlign: "center",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },

  checkIcon: {
    display: "inline-block",
    width: "64px",
    height: "64px",
    lineHeight: "64px",
    backgroundColor: "#D1FAE5",
    color: "#10B981",
    borderRadius: "50%",
    fontSize: "2rem",
    marginBottom: "1rem",
  },

  anomalySection: {
    backgroundColor: "white",
    padding: "1.5rem",
    borderRadius: "12px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },

  sectionTitle: {
    margin: "0 0 1.5rem 0",
    fontSize: "1.25rem",
    fontWeight: "600",
    color: "#111827",
  },

  anomalyList: {
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },

  anomalyCard: {
    backgroundColor: "#F9FAFB",
    border: "1px solid #E5E7EB",
    borderRadius: "8px",
    padding: "1rem",
  },

  anomalyHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "1rem",
  },

  anomalyHeaderLeft: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    flexWrap: "wrap",
  },

  anomalyNumber: {
    fontSize: "0.875rem",
    fontWeight: "600",
    color: "#6B7280",
  },

  severityBadge: {
    padding: "0.25rem 0.75rem",
    borderRadius: "4px",
    fontSize: "0.75rem",
    fontWeight: "700",
    border: "1px solid",
  },

  confidence: {
    fontSize: "0.875rem",
    color: "#6B7280",
  },

  expandButton: {
    width: "32px",
    height: "32px",
    borderRadius: "6px",
    border: "1px solid #D1D5DB",
    backgroundColor: "white",
    cursor: "pointer",
    fontSize: "1.25rem",
    fontWeight: "600",
    color: "#4B5563",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },

  anomalyContent: {
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },

  explanation: {
    color: "#374151",
    lineHeight: "1.6",
  },

  logSnippet: {
    marginTop: "0.5rem",
  },

  snippetHeader: {
    fontSize: "0.875rem",
    fontWeight: "600",
    color: "#6B7280",
    marginBottom: "0.5rem",
  },

  snippetCode: {
    backgroundColor: "#1F2937",
    color: "#D1D5DB",
    padding: "1rem",
    borderRadius: "6px",
    fontSize: "0.875rem",
    overflowX: "auto",
    margin: 0,
    fontFamily: '"Fira Code", "Courier New", monospace',
    lineHeight: "1.5",
  },

  errorCard: {
    backgroundColor: "#FEE2E2",
    border: "1px solid #FCA5A5",
    borderRadius: "12px",
    padding: "1.5rem",
    display: "flex",
    gap: "1rem",
    alignItems: "flex-start",
  },

  errorIcon: {
    width: "40px",
    height: "40px",
    backgroundColor: "#DC2626",
    color: "white",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "1.25rem",
    fontWeight: "700",
    flexShrink: 0,
  },

  errorTitle: {
    margin: "0 0 0.5rem 0",
    fontSize: "1rem",
    fontWeight: "600",
    color: "#991B1B",
  },

  errorMessage: {
    margin: 0,
    color: "#7F1D1D",
  },

  footer: {
    textAlign: "center",
    padding: "2rem",
    color: "#6B7280",
    fontSize: "0.875rem",
  },
};

// Add spinner animation
const styleSheet = document.createElement("style");
styleSheet.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(styleSheet);

export default App;
