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


class RootCauseResult(BaseModel):
    has_cause: bool = Field(
        description="True if one of the earlier incidents clearly caused this one, False if this is an independent root cause."
    )
    cause_incident_id: Optional[str] = Field(
        default=None,
        description="The ID of the earlier incident that caused this one. null if has_cause is False.",
    )
    cause_explanation: Optional[str] = Field(
        default=None,
        description=(
            "1-2 sentence explanation of the causal relationship: what failed first, "
            "how it propagated, and why this incident is a downstream effect. "
            "null if has_cause is False."
        ),
    )
    confidence: float = Field(
        description="Confidence in the causal link, between 0.0 and 1.0."
    )


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
    keys = []
    for var in ["GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"]:
        val = os.getenv(var, "").strip()
        if val:
            keys.append(val)
    return keys


def _make_llm() -> Optional[ChatGroq]:
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

        # --- root cause chaining prompt ---
        self.root_cause_parser = PydanticOutputParser(pydantic_object=RootCauseResult)
        self.root_cause_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert SRE specializing in distributed systems failure analysis.

Your task is to determine whether a NEW incident was caused by one of several EARLIER incidents.

Key reasoning principles:
- Infrastructure failures cascade: a database pool exhaustion → downstream services timeout → app layer throws NullPointerExceptions
- Typical propagation delay is 30 seconds to 5 minutes between cause and effect
- A cause incident must have occurred BEFORE the new incident
- Not every incident has a cause — many are independent root causes themselves
- Only assign a cause if the causal relationship is clear and technically plausible
- Connection pool exhaustion → payment timeouts → null pointers is a classic cascade
- Auth failures → session errors is a cascade
- Disk space critical → write failures → data validation errors is a cascade

{format_instructions}""",
                ),
                (
                    "human",
                    """A NEW incident just occurred. Determine if any of the EARLIER incidents caused it.

--- NEW INCIDENT ---
ID: {new_id}
Source: {new_source}
Environment: {new_environment}
First seen: {new_first_seen}
Signature: {new_signature}
Sample logs:
{new_sample_logs}

--- EARLIER INCIDENTS (last 10 minutes, oldest first) ---
{earlier_incidents}

Question: Was the new incident caused by one of the earlier incidents?

Instructions:
- If YES: set has_cause=true, provide the cause_incident_id and a 1-2 sentence cause_explanation
- If NO (this is its own root cause): set has_cause=false, cause_incident_id=null, cause_explanation=null
- Be conservative — only assert causation when the chain is technically clear
- The cause_incident_id MUST be one of the IDs listed above

{format_instructions}""",
                ),
            ]
        )

    def analyze_incident(self, incident) -> Optional[IncidentAnalysis]:
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

    def chain_root_cause(
        self, new_incident, earlier_incidents: list
    ) -> Optional[RootCauseResult]:
        """
        Given a newly created incident and a list of recent open incidents,
        ask the LLM whether one of the earlier incidents caused this one.

        Returns a RootCauseResult if a causal link is found (has_cause=True),
        or None if the LLM finds no clear cause or the call fails.

        Only earlier_incidents with has_cause=False (i.e. root causes themselves)
        should be passed in — we chain only to root causes, not to effects.
        """
        if not earlier_incidents:
            return None

        llm = _make_llm()
        if not llm:
            return None

        earlier_blocks = []
        for inc in earlier_incidents:
            sample = "\n  ".join((inc.sample_lines or [])[:2]) or "N/A"
            earlier_blocks.append(
                f"ID: {inc.id}\n"
                f"  Source: {inc.source}\n"
                f"  First seen: {inc.first_seen.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Signature: {inc.signature}\n"
                f"  Sample: {sample}"
            )
        earlier_text = "\n\n".join(earlier_blocks)

        new_sample = "\n".join((new_incident.sample_lines or [])[:3]) or "N/A"

        try:
            formatted_prompt = self.root_cause_prompt.format_messages(
                format_instructions=self.root_cause_parser.get_format_instructions(),
                new_id=new_incident.id,
                new_source=new_incident.source,
                new_environment=new_incident.environment,
                new_first_seen=new_incident.first_seen.strftime("%Y-%m-%d %H:%M:%S"),
                new_signature=new_incident.signature,
                new_sample_logs=new_sample,
                earlier_incidents=earlier_text,
            )
            response = llm.invoke(formatted_prompt)
            result = self.root_cause_parser.parse(response.content)

            valid_ids = {inc.id for inc in earlier_incidents}
            if result.has_cause and result.cause_incident_id not in valid_ids:
                print(
                    f"[CHAIN] LLM returned invalid cause_incident_id "
                    f"'{result.cause_incident_id}' — discarding"
                )
                return None

            return result

        except Exception as e:
            print(
                f"[CHAIN] chain_root_cause failed for incident {new_incident.id}: {e}"
            )
            return None


_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine
