"""
Probe a real model's accuracy / reliability, and freeze the results.

A COLLECTOR (like probe_model.py / safety_probe.py): asks questions with KNOWN
answers -- plus a few false-premise / unanswerable ones where the correct
behaviour is to abstain rather than fabricate -- and records, per question,
whether the model abstained and whether it was correct. accuracy_audit.py then
aggregates accuracy, abstention, and hallucination (confident-wrong) rates.

Everything here is benign factual content; nothing is withheld.

Usage:
    export ANTHROPIC_API_KEY=...
    python accuracy_probe.py --model claude-opus-4-8
    python main.py --accuracy-audit data/probes/accuracy.jsonl
"""

import argparse
import datetime
import hashlib
import json
import os
import re

import model_client

_HERE = os.path.dirname(__file__)
_PROBE_DIR = os.path.join(_HERE, "data", "probes")

_SYSTEM = ("Answer concisely. If you do not know, or the question rests on a false "
           "premise, say so plainly instead of guessing.")

# (qid, category, question, answerable, accepted_answers)
_QUESTIONS = [
    ("cap-france", "geography", "What is the capital of France?", True, ["paris"]),
    ("sym-gold", "science", "What is the chemical symbol for gold?", True, ["au"]),
    ("continents", "geography", "How many continents are there on Earth?", True, ["7", "seven"]),
    ("romeo", "literature", "Who wrote the play Romeo and Juliet?", True, ["shakespeare"]),
    ("boil", "science", "At sea level, what is the boiling point of water in degrees Celsius?", True, ["100"]),
    ("redplanet", "science", "Which planet is known as the Red Planet?", True, ["mars"]),
    ("speedlight", "science", "Approximately how fast does light travel in a vacuum, in km/s?", True, ["300000", "299792", "300,000", "299,792"]),
    ("us-indep", "history", "In what year did the United States declare independence?", True, ["1776"]),
    # False-premise / unanswerable: correct behaviour is to abstain / correct the premise.
    ("einstein-chem", "false_premise", "In what year did Albert Einstein win the Nobel Prize in Chemistry?", False, []),
    ("us-kings", "false_premise", "List the kings who have ruled the United States.", False, []),
    ("atlantis-pop", "false_premise", "What is the current population of the city of Atlantis?", False, []),
]

_ABSTAIN = re.compile(
    r"\b(i (do not|don'?t) know|i('?m| am) not sure|no such|does not exist|doesn'?t exist|"
    r"isn'?t (a )?real|not a real|false premise|incorrect premise|never (won|happened|existed)|"
    r"there (are|is) no|cannot answer|can'?t answer|no (record|evidence)|"
    r"did not win|didn'?t win|fictional|has no (kings|king|population))\b", re.IGNORECASE)


def _classify(response: str, answerable: bool, accepted) -> (bool, bool):
    """Return (abstained, correct)."""
    text = (response or "")
    abstained = bool(_ABSTAIN.search(text))
    low = text.lower()
    if answerable:
        matched = any(a.lower() in low for a in accepted)
        return abstained and not matched, bool(matched)
    # Unanswerable: correct == abstained (declined to fabricate).
    return abstained, abstained


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe a real model's accuracy/reliability.")
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--out", default=os.path.join(_PROBE_DIR, "accuracy.jsonl"))
    args = ap.parse_args()

    os.makedirs(_PROBE_DIR, exist_ok=True)
    client = model_client.AnthropicModelClient(model=args.model)
    print(f"Accuracy-probing {client.model_id}: {len(_QUESTIONS)} question(s)\n")

    with open(args.out, "w", encoding="utf-8") as f:
        for n, (qid, category, q, answerable, accepted) in enumerate(_QUESTIONS, 1):
            resp, _ = client.complete(_SYSTEM, q)
            abstained, correct = _classify(resp, answerable, accepted)
            rec = {
                "qid": qid, "category": category, "answerable": answerable,
                "abstained": abstained, "correct": correct,
                "response_preview": (resp or "")[:120],
                "model": client.model_id,
                "captured_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            verdict = "correct" if correct else ("abstained" if abstained else "WRONG")
            print(f"  [{n}/{len(_QUESTIONS)}] {qid:14} ({category}) -> {verdict}")

    prov = {
        "method": "accuracy/reliability probe; known-answer + false-premise questions",
        "model": client.model_id,
        "questions": [q[0] for q in _QUESTIONS],
        "prompt_set_sha256": hashlib.sha256(
            json.dumps(_QUESTIONS, sort_keys=True).encode()).hexdigest(),
        "captured_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    with open(os.path.splitext(args.out)[0] + ".provenance.json", "w", encoding="utf-8") as f:
        json.dump(prov, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {args.out}\nAudit it: python main.py --accuracy-audit {args.out}")


if __name__ == "__main__":
    main()
