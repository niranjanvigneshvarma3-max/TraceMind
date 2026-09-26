from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimelineEvent(StrictModel):
    event: str
    evidence_ids: list[str]


class Hypothesis(StrictModel):
    title: str
    explanation: str
    supporting_ids: list[str]
    contradicting_ids: list[str]


class Investigation(StrictModel):
    summary: str
    insufficient_evidence: bool
    timeline: list[TimelineEvent]
    hypotheses: list[Hypothesis]
    missing_information: list[str]
    next_checks: list[str]


class InvestigateRequest(StrictModel):
    case_id: str
    question: str = Field(min_length=5, max_length=1000)
    provider: str = Field(default="ollama", pattern="^(ollama|openai)$")
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|keyword|vector)$")

