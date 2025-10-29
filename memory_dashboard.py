import streamlit as st
import json
import pandas as pd
import os
from datetime import datetime, timezone
from collections import Counter

INCIDENT_FILE = "incidents.json"


def load_data():
    if not os.path.exists(INCIDENT_FILE):
        return pd.DataFrame(
            columns=[
                "timestamp",
                "template_id",
                "log_line",
                "root_cause",
                "fix",
                "code_hint",
            ]
        )
    with open(INCIDENT_FILE, "r") as f:
        try:
            data = json.load(f)
            return pd.DataFrame(data)
        except json.JSONDecodeError:
            return pd.DataFrame()


def time_since(ts_str):
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        days = delta.days
        hours = delta.seconds // 3600
        if days > 0:
            return f"{days}d {hours}h ago"
        return f"{hours}h ago"
    except Exception:
        return "—"


def badge_for_line(line: str) -> str:
    if "CRITICAL" in line:
        return "🔴 CRITICAL"
    elif "ERROR" in line:
        return "🟠 ERROR"
    elif "WARNING" in line:
        return "🟡 WARNING"
    else:
        return "🟢 INFO"


def render_summary(df):
    st.subheader("Learning Summary")

    total_incidents = len(df)
    unique_templates = df["template_id"].nunique()
    top_templates = df["template_id"].value_counts().head(5)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Incidents", total_incidents)
    col2.metric("Unique Patterns", unique_templates)
    col3.metric(
        "Recurring Template",
        str(top_templates.index[0]) if not top_templates.empty else "—",
    )

    st.markdown("### Top 5 Recurring Failure Templates")
    for tid, count in top_templates.items():
        subset = df[df["template_id"] == tid]
        example = subset.iloc[-1]["log_line"]
        st.markdown(f"**Template {tid}** — {count} occurrences")
        st.code(example, language="bash")


def render_severity_chart(df):
    st.subheader("Severity Frequency")
    severity_counts = Counter(
        (
            "CRITICAL"
            if "CRITICAL" in l
            else "ERROR" if "ERROR" in l else "WARNING" if "WARNING" in l else "INFO"
        )
        for l in df["log_line"]
    )
    chart_df = pd.DataFrame.from_dict(
        severity_counts, orient="index", columns=["count"]
    ).reset_index()
    chart_df.columns = ["Severity", "Count"]
    st.bar_chart(chart_df.set_index("Severity"))


def render_recent(df, keyword_filter=""):
    st.subheader("Recent Incidents")

    if keyword_filter:
        df = df[
            df.apply(
                lambda row: keyword_filter.lower() in row.to_string().lower(), axis=1
            )
        ]

    df = (
        df.sort_values("timestamp", ascending=False)
        .drop_duplicates(subset=["timestamp"])
        .head(15)
    )
    for _, row in df.iterrows():
        sev_badge = badge_for_line(row["log_line"])
        st.markdown(f"#### {sev_badge} — {row['log_line']}")
        st.caption(f"Template {row['template_id']} | ⏱ {time_since(row['timestamp'])}")
        st.markdown(f"**Root cause:** {row['root_cause']}")
        st.markdown(f"**Fix:** {row['fix']}")
        if row.get("code_hint"):
            st.caption(f"💡 {row['code_hint']}")
        st.markdown("---")


def main():
    st.set_page_config(page_title="LogSage RCA Memory Explorer", layout="wide")
    st.title("🧠 LogSage RCA Memory Explorer")

    df = load_data()
    if df.empty:
        st.warning("No incidents recorded yet. Run LogSage once to populate memory.")
        return

    with st.sidebar:
        st.header("🔍 Filters")
        keyword = st.text_input("Search (keyword, file, or error type):", "")
        st.markdown("---")
        st.caption(
            "Use this dashboard to explore recurring failures, severity patterns, and how LogSage learns over time."
        )

    render_summary(df)
    render_severity_chart(df)
    render_recent(df, keyword)


if __name__ == "__main__":
    main()
