"""
Pluggable evaluation harness.

An evaluator takes an audit context and returns one finding. The four-fifths
tabular bias audit is no longer special-cased -- it is one evaluator among many,
and a model-behaviour probe is another. New checks (recommender amplification,
privacy/data-protection, an LLM safety/refusal probe, ...) drop in by writing one
Evaluator subclass and registering it; engine.py runs whatever is registered.

Each evaluator declares what it needs and returns status="not run" when its
inputs are absent, so the harness can always run the full registry and report
which checks fired.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

import accuracy_audit
import bias_audit
import injection_audit
import model_audit
import privacy_audit
import recommender_audit
import safety_audit


@dataclass
class EvalContext:
    """Everything an evaluator might draw on for one audited system."""
    # Tabular bias-audit inputs (the user's own historical decision CSV).
    bias_df: Optional[pd.DataFrame] = None
    bias_outcome_col: Optional[str] = None
    bias_group_cols: Optional[List[str]] = None
    bias_mode: str = "selection"
    bias_min_share: float = 0.0
    # Model-probe input (a frozen transcript of real model decisions).
    model_transcript_path: Optional[str] = None
    # Privacy / re-identification (k-anonymity over quasi-identifiers).
    privacy_df: Optional[pd.DataFrame] = None
    quasi_identifiers: Optional[List[str]] = None
    k_threshold: int = 5
    # Recommender amplification (exposure log).
    recommender_df: Optional[pd.DataFrame] = None
    recommender_item_col: Optional[str] = None
    recommender_exposure_col: Optional[str] = None
    recommender_group_col: Optional[str] = None
    # LLM safety / refusal (a frozen safety-probe transcript).
    safety_transcript_path: Optional[str] = None
    # Accuracy / reliability (a frozen accuracy-probe transcript).
    accuracy_transcript_path: Optional[str] = None
    # Prompt-injection robustness (a frozen injection-probe transcript).
    injection_transcript_path: Optional[str] = None


@dataclass
class Evaluation:
    """One evaluator's finding, in a uniform, hashable shape."""
    evaluator_id: str
    title: str
    status: str            # "run" | "not run"
    result: Dict = field(default_factory=dict)
    reason: Optional[str] = None


class Evaluator:
    id: str = "base"
    title: str = "Base evaluator"

    def run(self, ctx: EvalContext) -> Evaluation:  # pragma: no cover - interface
        raise NotImplementedError


class TabularImpactRatioEvaluator(Evaluator):
    """NYC LL144 / four-fifths impact ratio on the user's own decision data."""
    id = "tabular-impact-ratio"
    title = "Disparate impact (four-fifths) on historical decisions"

    def run(self, ctx: EvalContext) -> Evaluation:
        if ctx.bias_df is None or not ctx.bias_outcome_col or not ctx.bias_group_cols:
            return Evaluation(self.id, self.title, "not run",
                              reason="No decision CSV supplied. Upload your own "
                                     "selection-decision data to run the LL144 bias audit.")
        result = bias_audit.run_bias_audit(
            ctx.bias_df, ctx.bias_outcome_col, ctx.bias_group_cols,
            mode=ctx.bias_mode, min_share=ctx.bias_min_share,
        )
        return Evaluation(self.id, self.title, "run", result=result)


class ModelDisparateTreatmentEvaluator(Evaluator):
    """Counterfactual / correspondence-test probe of a live model's decisions."""
    id = "model-disparate-treatment"
    title = "Disparate treatment probe of the model itself"

    def run(self, ctx: EvalContext) -> Evaluation:
        if not ctx.model_transcript_path:
            return Evaluation(self.id, self.title, "not run",
                              reason="No probe transcript supplied. Run probe_model.py "
                                     "against a real model, then audit the transcript.")
        result = model_audit.run_model_disparate_treatment_audit(ctx.model_transcript_path)
        if result.get("status") == "not run":
            return Evaluation(self.id, self.title, "not run", reason=result.get("reason"))
        return Evaluation(self.id, self.title, "run", result=result)


class PrivacyReidentificationEvaluator(Evaluator):
    """k-anonymity re-identification risk over quasi-identifiers."""
    id = "privacy-reidentification"
    title = "Re-identification risk (k-anonymity)"

    def run(self, ctx: EvalContext) -> Evaluation:
        if ctx.privacy_df is None or not ctx.quasi_identifiers:
            return Evaluation(self.id, self.title, "not run",
                              reason="No dataset + quasi-identifiers supplied for a "
                                     "k-anonymity privacy check.")
        result = privacy_audit.compute_k_anonymity(
            ctx.privacy_df, ctx.quasi_identifiers, k_threshold=ctx.k_threshold)
        if result.get("status") == "not run":
            return Evaluation(self.id, self.title, "not run", reason=result.get("reason"))
        return Evaluation(self.id, self.title, "run", result=result)


class RecommenderAmplificationEvaluator(Evaluator):
    """Exposure concentration + group disparity for recommender/ranking systems."""
    id = "recommender-amplification"
    title = "Recommender amplification (exposure concentration)"

    def run(self, ctx: EvalContext) -> Evaluation:
        if ctx.recommender_df is None or not ctx.recommender_item_col or not ctx.recommender_exposure_col:
            return Evaluation(self.id, self.title, "not run",
                              reason="No exposure log (item + exposure columns) supplied.")
        result = recommender_audit.compute_exposure_concentration(
            ctx.recommender_df, ctx.recommender_item_col, ctx.recommender_exposure_col,
            group_col=ctx.recommender_group_col)
        if result.get("status") == "not run":
            return Evaluation(self.id, self.title, "not run", reason=result.get("reason"))
        return Evaluation(self.id, self.title, "run", result=result)


class LLMSafetyEvaluator(Evaluator):
    """Refusal behaviour on harmful vs benign prompts (EU AI Act Art. 55)."""
    id = "llm-safety-refusal"
    title = "LLM safety / refusal behaviour"

    def run(self, ctx: EvalContext) -> Evaluation:
        if not ctx.safety_transcript_path:
            return Evaluation(self.id, self.title, "not run",
                              reason="No safety-probe transcript supplied. Run "
                                     "safety_probe.py against a real model.")
        result = safety_audit.run_safety_audit(ctx.safety_transcript_path)
        if result.get("status") == "not run":
            return Evaluation(self.id, self.title, "not run", reason=result.get("reason"))
        return Evaluation(self.id, self.title, "run", result=result)


class AccuracyReliabilityEvaluator(Evaluator):
    """Accuracy / hallucination on known-answer + false-premise questions (Art. 15)."""
    id = "accuracy-reliability"
    title = "Accuracy / reliability (incl. hallucination)"

    def run(self, ctx: EvalContext) -> Evaluation:
        if not ctx.accuracy_transcript_path:
            return Evaluation(self.id, self.title, "not run",
                              reason="No accuracy-probe transcript supplied. Run "
                                     "accuracy_probe.py against a real model.")
        result = accuracy_audit.run_accuracy_audit(ctx.accuracy_transcript_path)
        if result.get("status") == "not run":
            return Evaluation(self.id, self.title, "not run", reason=result.get("reason"))
        return Evaluation(self.id, self.title, "run", result=result)


class PromptInjectionEvaluator(Evaluator):
    """Prompt-injection robustness on untrusted content (EU AI Act Art. 15)."""
    id = "prompt-injection"
    title = "Prompt-injection robustness"

    def run(self, ctx: EvalContext) -> Evaluation:
        if not ctx.injection_transcript_path:
            return Evaluation(self.id, self.title, "not run",
                              reason="No injection-probe transcript supplied. Run "
                                     "injection_probe.py against a real model.")
        result = injection_audit.run_injection_audit(ctx.injection_transcript_path)
        if result.get("status") == "not run":
            return Evaluation(self.id, self.title, "not run", reason=result.get("reason"))
        return Evaluation(self.id, self.title, "run", result=result)


# The registry. Append an Evaluator subclass here to add a check.
REGISTRY: List[Evaluator] = [
    TabularImpactRatioEvaluator(),
    ModelDisparateTreatmentEvaluator(),
    PrivacyReidentificationEvaluator(),
    RecommenderAmplificationEvaluator(),
    LLMSafetyEvaluator(),
    AccuracyReliabilityEvaluator(),
    PromptInjectionEvaluator(),
]


def run_all(ctx: EvalContext) -> List[Evaluation]:
    return [ev.run(ctx) for ev in REGISTRY]
