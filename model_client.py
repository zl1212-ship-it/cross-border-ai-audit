"""
Model client abstraction for the probe layer.

A `ModelClient` makes one screening decision for one prompt and returns a
(decision, raw_json) pair. Two implementations:

  AnthropicModelClient  calls a real Claude model via the official Anthropic SDK,
                        using structured outputs so the decision is a clean,
                        schema-validated JSON object (no brittle text parsing).

  ReplayModelClient     replays decisions from a frozen transcript, keyed by the
                        probe cell id. Lets an audit be re-run offline and
                        deterministically against captured real responses -- the
                        same "verify against the saved copy" discipline used for
                        bot-blocked sources.

Nothing here fabricates a decision. AnthropicModelClient returns exactly what the
model returned; ReplayModelClient returns exactly what was captured and saved.
"""

import json
from typing import Dict, Optional, Tuple

# Schema for the model's screening decision (structured output -> no text parsing).
_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "advance": {"type": "boolean",
                    "description": "True to advance the candidate to a first-round interview."},
        "reason": {"type": "string", "description": "One-sentence justification."},
    },
    "required": ["advance", "reason"],
    "additionalProperties": False,
}


class ModelClient:
    """Interface: a screening decision, and a free-text completion."""

    model_id: str = "unknown"

    def decide(self, system: str, user: str) -> Tuple[int, str]:
        raise NotImplementedError

    def complete(self, system: str, user: str) -> Tuple[str, str]:
        """Return (response_text, stop_reason) for a free-text prompt."""
        raise NotImplementedError


class AnthropicModelClient(ModelClient):
    """Calls a real Claude model via the Anthropic SDK with structured outputs."""

    def __init__(self, model: str = "claude-opus-4-8", max_tokens: int = 1024):
        import anthropic  # imported lazily so the rest of the toolkit needs no key
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.model_id = model
        self.max_tokens = max_tokens

    def decide(self, system: str, user: str) -> Tuple[int, str]:
        resp = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": _DECISION_SCHEMA}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        data = json.loads(text)
        return (1 if data.get("advance") else 0), text

    def complete(self, system: str, user: str) -> Tuple[str, str]:
        resp = self.client.messages.create(
            model=self.model_id,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text, (resp.stop_reason or "")


class ReplayModelClient(ModelClient):
    """Replays captured decisions from a transcript, keyed by cell id."""

    def __init__(self, transcript_path: str):
        import model_audit
        self.model_id = "replay"
        self._by_cell: Dict[str, Dict] = {}
        for r in model_audit.load_transcript(transcript_path):
            self._by_cell[r["cell_id"]] = r

    def decide_cell(self, cell_id: str) -> Tuple[int, str]:
        r = self._by_cell[cell_id]
        return int(r["decision"]), r.get("raw", "")

    def decide(self, system: str, user: str) -> Tuple[int, str]:
        raise NotImplementedError("ReplayModelClient replays by cell_id; use decide_cell().")
