"""Structured contracts shared by the v2 parent and specialist graphs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

AgentName = Literal[
    "discovery",
    "spec_selection",
    "solution_advisory",
    "comparison",
    "compliance",
]
ReportStatus = Literal["complete", "partial", "no_result"]
Depth = Literal["overview", "detailed"]
# What the turn is asking for, decided by the planner because it is already
# reading the question and a separate classifier would cost another round trip.
# "company" is a real C&S enquiry this agent cannot serve — a job application, an
# order, a warranty claim, a dealer appointment. "unrelated" is everything with no
# C&S connection at all. Both leave the pipeline; only the wording differs.
Scope = Literal["catalogue", "company", "unrelated"]

# Depth the planner gets when it names none. Discovery answers "what do you have"
# questions, where the ranges themselves are the answer and detail belongs to a
# follow-up turn, so it starts shallow; the agents that exist to produce a
# shortlist, a table, or a scheme have nothing to say at overview depth.
DEFAULT_DEPTH: dict[str, Depth] = {"discovery": "overview"}


def brief_depth(brief: dict[str, Any]) -> str:
    """Read a dispatched brief's depth, defaulting the way the Plan does."""
    return brief.get("depth") or DEFAULT_DEPTH.get(brief.get("agent", ""), "detailed")


# Where a claim came from: one ordering code, or the range it describes. Not
# every retrieved fact belongs to a single product — `list_canonical_specs`
# answers at family level (which spec IDs a range publishes, over how many SKUs,
# between which observed bounds) and a `product_search` grouped by family answers
# "80 of 316 in scope match poles=4". Neither has a sku_code to give, so `family`
# is how such a claim states its scope. Requiring the SKU regardless left the
# model two ways out and it took both: attach some arbitrary member code to a
# claim about the whole range, or drop the claim.
#
# Docstrings are deliberately not used on the report contracts: the whole schema
# is dumped into the report prompt verbatim, so every line of prose here is paid
# for on every specialist report call.
class SourceRef(BaseModel):
    sku_code: str | None = None
    family: str | None = Field(
        None, description="Scope of a claim about a range rather than one product."
    )
    brochure_md: str | None = None
    pricelist_pdf: str | None = None
    pricelist_page: int | None = None
    product_page_url: str | None = None
    source_of_truth: str | None = None


class Finding(BaseModel):
    statement: str
    kind: Literal["specification", "catalogue", "price", "general"] = "catalogue"
    source: SourceRef | None = None


class AgentBrief(BaseModel):
    agent: AgentName
    objective: str
    stage: int = Field(1, ge=1)
    scope: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    must_return: list[str] = Field(default_factory=list)
    allowance: int = Field(0, ge=0)
    depth: Depth | None = None
    revision_note: str | None = None


class Plan(BaseModel):
    intent: str
    scope: Scope = "catalogue"
    # One line naming what the user actually wanted, for the reply to open on.
    # Only read when scope is not "catalogue".
    scope_note: str = ""
    # Empty only for an out-of-scope turn; `_require_dispatch_in_scope` holds
    # the floor of one for everything else.
    dispatch: list[AgentBrief] = Field(default_factory=list, max_length=5)
    known_params: dict[str, Any] = Field(default_factory=dict)
    open_params: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    strategy: str = ""

    @model_validator(mode="after")
    def _normalise_dispatch(self) -> "Plan":
        """Order the dispatch into contiguous stages with one brief per agent.

        A model asked to sequence agents readily emits sparse stage numbers
        (1 and 3) or lists an agent twice. Either would leave the runtime
        waiting on a stage that never runs, so renumber rather than reject:
        the ordering the planner intended survives, the gaps do not.

        Depth is settled here too, so a planner that omits it produces a cheap
        answer that invites a follow-up rather than an exhaustive sweep.
        """
        seen: set[str] = set()
        unique: list[AgentBrief] = []
        for brief in sorted(self.dispatch, key=lambda item: item.stage):
            if brief.agent in seen:
                continue
            seen.add(brief.agent)
            unique.append(brief)
        ranks = {
            stage: rank
            for rank, stage in enumerate(sorted({b.stage for b in unique}), start=1)
        }
        for brief in unique:
            brief.stage = ranks[brief.stage]
            if brief.depth is None:
                brief.depth = DEFAULT_DEPTH.get(brief.agent, "detailed")
        self.dispatch = unique
        return self

    @model_validator(mode="after")
    def _require_dispatch_in_scope(self) -> "Plan":
        """A catalogue question must dispatch somebody.

        `dispatch` cannot carry a minimum length any more, because an
        out-of-scope turn legitimately dispatches nothing. Enforcing it here
        instead keeps the guarantee where it matters and lets `structured()`
        retry, which a Field constraint would also do — but a Field constraint
        would additionally reject every valid refusal.
        """
        if self.scope == "catalogue" and not self.dispatch:
            raise ValueError(
                "dispatch must name at least one agent when scope is 'catalogue'"
            )
        return self


class KeySpec(BaseModel):
    spec_id: str
    value_display: str | None = None
    unit: str | None = None
    source: SourceRef | None = None


# A shortlist entry, addressed by ordering code or — failing that — range. The
# ordering code stays the deliverable whenever the brief asks for one, but a
# brief can legitimately stop at range level ("which families offer a 4-pole
# variant") and then there is no one code to name. The gate holds the floor: an
# entry naming neither is not an answer.
class Candidate(BaseModel):
    sku_code: str | None = None
    family: str | None = Field(
        None, description="Set instead of sku_code when the shortlist is range-level."
    )
    why_it_fits: str
    key_specs: list[KeySpec] = Field(default_factory=list)
    price_status: str | None = None


class FamilyBrief(BaseModel):
    name: str
    path: list[str] = Field(default_factory=list)
    description: str | None = None
    sku_count: int = 0
    url: str | None = None


class ComparisonTable(BaseModel):
    axes: list[str] = Field(default_factory=list)
    rows: dict[str, dict[str, Any]] = Field(default_factory=dict)


class StandardClaim(BaseModel):
    sku_code: str
    spec_id: str
    value_display: str
    source_of_truth: str | None = None
    source: SourceRef | None = None


class Claim(BaseModel):
    statement: str
    source: SourceRef | None = None


class Slot(BaseModel):
    function: str
    resolution: str
    family: str | None = None
    sku_code: str | None = None


class AgentReport(BaseModel):
    agent: AgentName
    status: ReportStatus
    summary: str = Field(max_length=1000)
    findings: list[Finding] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    tool_calls_used: int = Field(0, ge=0)
    caveats: list[str] = Field(default_factory=list)


class SpecSelectionReport(AgentReport):
    agent: Literal["spec_selection"] = "spec_selection"
    candidates: list[Candidate] = Field(default_factory=list)
    no_candidates_reason: str | None = None
    filters_tried: list[str] = Field(default_factory=list)


class DiscoveryReport(AgentReport):
    agent: Literal["discovery"] = "discovery"
    families: list[FamilyBrief] = Field(default_factory=list)
    representative_skus: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    uncategorised_note: str | None = None


class ComparisonReport(AgentReport):
    agent: Literal["comparison"] = "comparison"
    table: ComparisonTable = Field(default_factory=ComparisonTable)
    peer_group_match: bool = False
    differentiators: list[str] = Field(default_factory=list)


class ComplianceReport(AgentReport):
    agent: Literal["compliance"] = "compliance"
    standards: list[StandardClaim] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    not_established: list[str] = Field(default_factory=list)


class AdvisoryReport(AgentReport):
    agent: Literal["solution_advisory"] = "solution_advisory"
    catalog_backed: list[Claim] = Field(default_factory=list)
    engineering_guidance: list[Claim] = Field(default_factory=list)
    recommended_slots: list[Slot] = Field(default_factory=list)


REPORT_SCHEMAS: dict[str, type[AgentReport]] = {
    "discovery": DiscoveryReport,
    "spec_selection": SpecSelectionReport,
    "solution_advisory": AdvisoryReport,
    "comparison": ComparisonReport,
    "compliance": ComplianceReport,
}


class GateFailure(BaseModel):
    agent: AgentName
    violations: list[str]


class GateResult(BaseModel):
    ok: bool
    failures: list[GateFailure] = Field(default_factory=list)


class SufficiencyGap(BaseModel):
    agent: AgentName
    missing: str
    suggested_tool: str | None = None


class SufficiencyResult(BaseModel):
    sufficient: bool
    gaps: list[SufficiencyGap] = Field(default_factory=list)


class IntakeResult(BaseModel):
    standalone_question: str
    referenced_skus: list[str] = Field(default_factory=list)
    is_followup: bool = False
    carried_params: dict[str, Any] = Field(default_factory=dict)
