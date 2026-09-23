from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RuleLink:
    issue: str
    rule_or_policy: str
    why_it_matters: str
    evidence_needed: List[str]
    standard: str = "lawful review"


@dataclass
class NarrativePacket:
    issue: str
    summary: str
    supported_facts: List[str]
    inferences: List[str]
    counterevidence: List[str]
    unanswered_questions: List[str]
    next_steps: List[str]
    rules: List[RuleLink] = field(default_factory=list)


class LegalRelevanceEngine:
    """Links an issue to likely laws, policies, or procedures and prepares a defensible narrative packet."""

    RULE_SET = {
        "payment": [
            RuleLink(
                issue="payment",
                rule_or_policy="Procurement and payment controls",
                why_it_matters="Public funds should follow documented approvals, contractual terms, and auditability requirements.",
                evidence_needed=["contract", "approval record", "invoice", "payment ledger", "authorization"],
            )
        ],
        "contract": [
            RuleLink(
                issue="contract",
                rule_or_policy="Contracting and amendment procedures",
                why_it_matters="Contracts and amendments should be authorized, competition-sensitive, and subject to review if required by policy or law.",
                evidence_needed=["award record", "amendment file", "bid documentation", "signatures or approvals"],
            )
        ],
        "meeting": [
            RuleLink(
                issue="meeting",
                rule_or_policy="Open meeting and notice requirements",
                why_it_matters="Relevant meetings may require notice, attendance, agendas, and minutes to preserve public accountability.",
                evidence_needed=["agenda", "minutes", "attendance record", "notice"],
            )
        ],
        "permit": [
            RuleLink(
                issue="permit",
                rule_or_policy="Permitting and inspection protocol",
                why_it_matters="Permit approval and inspection history can reveal compliance or irregularities that require further review.",
                evidence_needed=["application", "inspection record", "approval", "correspondence"],
            )
        ],
        "fund": [
            RuleLink(
                issue="fund",
                rule_or_policy="Budget, grant, and fund-transfer controls",
                why_it_matters="Fund transfers should be consistent with the approving authority, program purpose, and documentation trail.",
                evidence_needed=["transfer record", "grant file", "budget approval", "reporting document"],
            )
        ],
    }

    def evidence_links(self, issue: str) -> List[RuleLink]:
        key = issue.lower().strip()
        return self.RULE_SET.get(key, [
            RuleLink(
                issue=issue,
                rule_or_policy="Applicable governing rule or procedure",
                why_it_matters="The issue requires a defined lawful standard before a conclusion is drawn.",
                evidence_needed=["policies", "procedures", "records", "approvals", "correspondence"],
            )
        ])

    def build_narrative_packet(self, issue: str, facts: List[str], inferences: List[str], counterevidence: List[str], unanswered_questions: Optional[List[str]] = None) -> NarrativePacket:
        packet = NarrativePacket(
            issue=issue,
            summary=f"A working narrative for {issue} is being developed under a review-first process.",
            supported_facts=list(facts),
            inferences=list(inferences),
            counterevidence=list(counterevidence),
            unanswered_questions=list(unanswered_questions or []),
            next_steps=[
                "Confirm that the records and approvals exist in the official source.",
                "Check for contradictory or exculpatory evidence.",
                "Obtain the missing record set and assess whether the issue remains material.",
            ],
            rules=self.evidence_links(issue),
        )
        return packet

    def summarize_issue(self, issue: str, facts: List[str], inferences: List[str], counterevidence: List[str]) -> Dict[str, Any]:
        packet = self.build_narrative_packet(issue, facts, inferences, counterevidence)
        return {
            "issue": packet.issue,
            "summary": packet.summary,
            "supported_facts": packet.supported_facts,
            "inferences": packet.inferences,
            "counterevidence": packet.counterevidence,
            "questions": packet.unanswered_questions,
            "next_steps": packet.next_steps,
            "linked_rules": [
                {
                    "rule_or_policy": item.rule_or_policy,
                    "why_it_matters": item.why_it_matters,
                    "evidence_needed": item.evidence_needed,
                }
                for item in packet.rules
            ],
        }
