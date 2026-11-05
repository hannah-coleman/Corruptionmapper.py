# server.py

# Import the ReviewEngine class
from review_engine import ReviewEngine

from http.server import SimpleHTTPRequestHandler
from pathlib import Path

class SignalLedgerHandler(SimpleHTTPRequestHandler):
    def review_fact_record(self, route: str) -> None:
        try:
            body = self.read_json_object()
            engine = ReviewEngine(Path("evidence/claims.json"), Path("evidence/records.json"), Path("evidence/audit.jsonl"))
            fact_id = route.removeprefix("/api/facts/").removesuffix("/review")
            fact = engine.review_fact(fact_id, body["reviewer"], body["disposition"], body["rationale"], body["next_action"])
        except (ValueError, KeyError) as error:
            self.send_json({"error": str(error)}, 400)
            return
        self.send_json({"status": "ok", "record": fact})
    # ... other methods ...

    def review_fact_record(self, route: str) -> None:
        try:
            body = self.read_json_object()
            engine = ReviewEngine(
                Path("evidence/claims.json"),
                Path("evidence/records.json"),
                Path("evidence/audit.json"),
            )
            fact_id = route.removeprefix("/api/facts/").removesuffix("/review")
            fact = engine.review_fact(
                fact_id,
                body["reviewer"],
                body["disposition"],
                body["rationale"],
                body["next_action"],
            )
            self.send_json({"status": "ok", "record": fact})
        except (ValueError, KeyError) as error:
            self.send_json({"error": str(error)}, 400)