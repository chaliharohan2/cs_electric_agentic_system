"""The CS Electric support agent.

This is the "agentic" core of the system: given the natural-language content of
a support ticket, it triages the request (category + priority) and drafts a
reply for the customer.

The default implementation is a deterministic, rule-based agent so the system
runs end-to-end with no external dependencies or secrets. It is intentionally
structured so a large-language-model backend can be dropped in later behind the
same :meth:`SupportAgent.handle` interface.
"""
from __future__ import annotations

from dataclasses import dataclass

# Ordered by specificity: the first category whose keywords match wins.
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("outage", ("outage", "power out", "no power", "blackout", "down", "no electricity")),
    ("billing", ("bill", "invoice", "charge", "payment", "refund", "overcharged", "tariff")),
    ("safety", ("spark", "fire", "smoke", "burning", "shock", "exposed wire", "hazard")),
    ("connection", ("connect", "new connection", "meter", "install", "hook up", "supply")),
    ("technical", ("voltage", "flicker", "fluctuat", "breaker", "fuse", "surge")),
]

# Words that bump a ticket to high/urgent priority.
_URGENT_KEYWORDS = ("fire", "smoke", "spark", "shock", "burning", "hazard", "emergency")
_HIGH_KEYWORDS = ("outage", "no power", "no electricity", "blackout", "urgent", "asap")


@dataclass
class Triage:
    category: str
    priority: str


class SupportAgent:
    """Rule-based triage + reply agent for CS Electric support tickets."""

    def triage(self, subject: str, body: str) -> Triage:
        text = f"{subject}\n{body}".lower()

        category = "general"
        for name, keywords in _CATEGORY_KEYWORDS:
            if any(k in text for k in keywords):
                category = name
                break

        priority = "normal"
        if any(k in text for k in _URGENT_KEYWORDS) or category == "safety":
            priority = "urgent"
        elif any(k in text for k in _HIGH_KEYWORDS) or category == "outage":
            priority = "high"

        return Triage(category=category, priority=priority)

    def draft_reply(self, customer_name: str, triage: Triage, subject: str) -> str:
        greeting = f"Hi {customer_name.split()[0] if customer_name else 'there'},"

        openings = {
            "outage": "Thank you for reporting the power outage. We've logged this and our "
            "field team has been notified to investigate supply in your area.",
            "billing": "Thanks for reaching out about your billing query. Our accounts team "
            "will review your invoice and get back to you with a detailed breakdown.",
            "safety": "This has been flagged as a safety-critical issue. Please stay clear of "
            "the affected equipment. A CS Electric safety technician has been dispatched "
            "as a priority.",
            "connection": "Thanks for your enquiry about your connection. We'll review the "
            "details and a connections specialist will follow up with next steps.",
            "technical": "Thanks for the technical report. We've recorded the details and an "
            "engineer will assess the issue on your supply.",
            "general": "Thanks for contacting CS Electric support. We've received your "
            "request and a support specialist will be in touch shortly.",
        }

        sla = {
            "urgent": "Because this is urgent, you can expect an update within 1 hour.",
            "high": "You can expect an update within 4 hours.",
            "normal": "You can expect an update within 1 business day.",
        }

        body = openings.get(triage.category, openings["general"])
        return (
            f"{greeting}\n\n"
            f"{body}\n\n"
            f"{sla[triage.priority]}\n\n"
            f"Reference subject: {subject}\n\n"
            "Kind regards,\nCS Electric Support Agent"
        )

    def handle(self, customer_name: str, subject: str, body: str) -> tuple[Triage, str]:
        """Triage a ticket and return the triage result plus a drafted reply."""
        triage = self.triage(subject, body)
        reply = self.draft_reply(customer_name, triage, subject)
        return triage, reply

    def follow_up(self, customer_name: str, category: str, message_body: str) -> str:
        """Draft a reply to a follow-up message on an existing ticket."""
        greeting = f"Hi {customer_name.split()[0] if customer_name else 'there'},"
        return (
            f"{greeting}\n\n"
            "Thanks for the additional information. We've added it to your ticket and "
            "the assigned specialist has been notified.\n\n"
            "Kind regards,\nCS Electric Support Agent"
        )


# Module-level singleton used by the routes.
agent = SupportAgent()
