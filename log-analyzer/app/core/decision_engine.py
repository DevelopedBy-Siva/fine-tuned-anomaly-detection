import os
import random
from typing import Optional
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class IncidentAnalysis(BaseModel):
    severity: str = Field(description="Severity level: low, medium, high, or critical")
    disposition: str = Field(
        description="Action to take: NO_ACTION, OBSERVE, NEEDS_DEV, NEEDS_ONCALL, or ESCALATE"
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    summary: str = Field(description="2-3 sentence summary of the issue")
    next_steps: list[str] = Field(
        description="3-5 concrete action items to resolve or investigate"
    )
    ticket_title: str = Field(description="Concise ticket title (max 100 chars)")
    ticket_body: str = Field(description="Detailed ticket description for developers")


def validate_analysis(analysis: IncidentAnalysis, incident) -> IncidentAnalysis:
    critical_patterns = [
        "outofmemoryerror",
        "heap space",
        "segmentation fault",
        "segfault",
        "core dumped",
        "fatal error",
        "stack overflow",
    ]
    high_patterns = [
        "database connection",
        "connection refused",
        "timeout",
        "null pointer",
        "exception",
        "failed to connect",
        "connection pool",
    ]

    sample_text = " ".join(incident.sample_lines or []).lower()
    full_text = f"{incident.signature.lower()} {sample_text}"

    if any(pattern in full_text for pattern in critical_patterns):
        if analysis.severity not in ["critical", "high"]:
            analysis.severity = "critical"
        if analysis.disposition not in ["ESCALATE", "NEEDS_ONCALL"]:
            analysis.disposition = "ESCALATE"
    elif any(pattern in full_text for pattern in high_patterns):
        if analysis.severity == "low":
            analysis.severity = "high"

    analysis.severity = analysis.severity.lower().strip()
    analysis.disposition = analysis.disposition.upper().strip()

    if analysis.severity == "critical" and analysis.disposition not in [
        "ESCALATE",
        "NEEDS_ONCALL",
    ]:
        analysis.disposition = "ESCALATE"
    if analysis.severity == "high" and analysis.disposition not in [
        "ESCALATE",
        "NEEDS_ONCALL",
        "NEEDS_DEV",
    ]:
        analysis.disposition = "NEEDS_ONCALL"
    if analysis.disposition == "ESCALATE" and analysis.severity not in [
        "critical",
        "high",
    ]:
        analysis.severity = "high"

    analysis.confidence = max(0.0, min(1.0, analysis.confidence))

    if not analysis.ticket_title or not analysis.ticket_title.strip():
        analysis.ticket_title = f"{incident.source} - {incident.signature[:50]}"
    if len(analysis.ticket_title) > 100:
        analysis.ticket_title = analysis.ticket_title[:97] + "..."

    return analysis


def _get_groq_keys() -> list[str]:
    """
    Collect all configured Groq API keys.
    Env vars: GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3
    Any that are set and non-empty are included.
    """
    keys = []
    for var in ["GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"]:
        val = os.getenv(var, "").strip()
        if val:
            keys.append(val)
    return keys


def _make_llm() -> Optional[ChatGroq]:
    """Pick a random key and return a ChatGroq client."""
    keys = _get_groq_keys()
    if not keys:
        print("Warning: No GROQ_API_KEY found. LLM analysis disabled.")
        return None
    key = random.choice(keys)
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=key,
    )


class DecisionEngine:
    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=IncidentAnalysis)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert SRE analyzing production incidents.

Your job is to:
1. Assess the severity of the issue
2. Recommend the appropriate action (disposition)
3. Provide clear next steps for resolution
4. Draft a ticket for the development team

Severity guidelines:
- CRITICAL: Service down, data loss, security breach, OutOfMemoryError, heap space errors, segfaults, fatal errors, affects all users
- HIGH: Major feature broken, database connection errors, null pointer exceptions, affects many users, revenue impact
- MEDIUM: Feature partially broken, intermittent errors, affects some users, has workarounds
- LOW: Minor issue, cosmetic, logging errors, affects few users

Disposition guidelines (must align with severity):
- ESCALATE: ONLY for CRITICAL/HIGH severity - requires immediate attention (page on-call)
- NEEDS_ONCALL: For HIGH severity - notify on-call engineer during business hours
- NEEDS_DEV: For MEDIUM/HIGH severity - standard development ticket needed
- OBSERVE: For LOW/MEDIUM severity - monitor for patterns, only act if it repeats
- NO_ACTION: For LOW severity - known noise, safe to ignore

**CRITICAL RULES**: 
- If severity is CRITICAL or HIGH → disposition MUST be ESCALATE or NEEDS_ONCALL
- OutOfMemoryError, heap space errors, segfaults, fatal errors → ALWAYS CRITICAL severity with ESCALATE disposition
- Database connection errors, null pointer exceptions → ALWAYS HIGH severity minimum
- If disposition is ESCALATE → severity MUST be CRITICAL or HIGH
- ALWAYS provide a ticket_title (never null or empty)

{format_instructions}""",
                ),
                (
                    "human",
                    """Analyze this incident:

**Source Service:** {source}
**Environment:** {environment}
**Occurrence Count:** {count}
**First Seen:** {first_seen}
**Last Seen:** {last_seen}

**Sample Error Logs:**
{sample_logs}

Provide a structured analysis with severity, disposition, summary, next steps, and ticket draft.

IMPORTANT REMINDERS:
- OutOfMemoryError and heap space errors are ALWAYS CRITICAL severity with ESCALATE disposition
- Database connection errors are ALWAYS HIGH severity minimum
- Always provide a ticket_title (never leave it null or empty)
- Ensure severity and disposition are aligned""",
                ),
            ]
        )

    def analyze_incident(self, incident) -> Optional[IncidentAnalysis]:
        # fresh random key on every call — rotates across all configured keys
        llm = _make_llm()
        if not llm:
            return None

        try:
            sample_logs = (
                "\n".join(incident.sample_lines[:3]) if incident.sample_lines else "N/A"
            )
            formatted_prompt = self.prompt.format_messages(
                format_instructions=self.parser.get_format_instructions(),
                source=incident.source,
                environment=incident.environment,
                count=incident.count,
                first_seen=incident.first_seen.strftime("%Y-%m-%d %H:%M:%S"),
                last_seen=incident.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
                sample_logs=sample_logs,
            )
            response = llm.invoke(formatted_prompt)
            analysis = self.parser.parse(response.content)
            analysis = validate_analysis(analysis, incident)
            return analysis

        except Exception as e:
            print(f"LLM analysis failed: {e}")
            return None


_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine
