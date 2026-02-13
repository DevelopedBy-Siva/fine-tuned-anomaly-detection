import os
from typing import Optional
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class IncidentAnalysis(BaseModel):
    """Structured output from LLM"""

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


class DecisionEngine:
    """LangChain-based decision engine for incident analysis"""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("⚠️  Warning: GROQ_API_KEY not found. LLM analysis disabled.")
            self.llm = None
            return

        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",  # Fast and capable model
            temperature=0.3,  # Lower temperature for more consistent outputs
            api_key=api_key,
        )

        self.parser = PydanticOutputParser(pydantic_object=IncidentAnalysis)

        # Prompt template
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
- CRITICAL: Service down, data loss, security breach, affects all users
- HIGH: Major feature broken, affects many users, revenue impact
- MEDIUM: Feature partially broken, affects some users, has workarounds
- LOW: Minor issue, cosmetic, affects few users

Disposition guidelines:
- ESCALATE: Critical issue requiring immediate attention (page on-call)
- NEEDS_ONCALL: High priority, notify on-call engineer
- NEEDS_DEV: Standard development ticket needed
- OBSERVE: Monitor for patterns, only act if it repeats
- NO_ACTION: Known noise, safe to ignore

Be concise, actionable, and technical.

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

Provide a structured analysis with severity, disposition, summary, next steps, and ticket draft.""",
                ),
            ]
        )

    def analyze_incident(self, incident) -> Optional[IncidentAnalysis]:
        """
        Analyze an incident using LLM and return structured output.

        Returns None if LLM is not configured or analysis fails.
        """
        if not self.llm:
            return None

        try:
            # Prepare sample logs (first 3 samples)
            sample_logs = (
                "\n".join(incident.sample_lines[:3]) if incident.sample_lines else "N/A"
            )

            # Format the prompt
            formatted_prompt = self.prompt.format_messages(
                format_instructions=self.parser.get_format_instructions(),
                source=incident.source,
                environment=incident.environment,
                count=incident.count,
                first_seen=incident.first_seen.strftime("%Y-%m-%d %H:%M:%S"),
                last_seen=incident.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
                sample_logs=sample_logs,
            )

            # Call LLM
            response = self.llm.invoke(formatted_prompt)

            # Parse structured output
            analysis = self.parser.parse(response.content)

            return analysis

        except Exception as e:
            print(f"❌ LLM analysis failed: {e}")
            return None


# Singleton instance
_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Get or create singleton decision engine"""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine
