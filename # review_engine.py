# review_engine.py

class ReviewEngine:
    def __init__(self, claims_path, evidence_path, audit_path):
        self.claims_path = claims_path
        self.evidence_path = evidence_path
        self.audit_path = audit_path

    def review_claim(self, claim_id, reviewer, disposition, rationale, next_action):
        # Add your code here to review a claim
        pass

    def review_fact(self, fact_id, reviewer, disposition, rationale, next_action):
        # Add your code here to review a fact
        pass