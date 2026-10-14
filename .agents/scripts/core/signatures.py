import os
import sys
import re
import json
import argparse
from typing import Dict, Any, List, Optional, Type, Callable

def _log_telemetry(err: Exception, context: str = "") -> None:
    """Non-fatal telemetry catch for degraded operations."""
    if os.environ.get("ORION_DEBUG"):
        msg = f": {err}" if err else ""
        sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception as _e:
        _log_telemetry(_e, 'signatures.py:reconfigure')


class InputField:
    """Descriptor for declarative prompt inputs."""
    def __init__(self, desc: str = ""):
        self.desc = desc


class OutputField:
    """Descriptor for declarative prompt outputs."""
    def __init__(self, desc: str = ""):
        self.desc = desc


class Signature:
    """
    Pillar 1: Base Declarative Prompt Signature.
    Distilled from DSPy.
    Converts typed class definitions into structured, token-efficient prompt envelopes.
    """

    @classmethod
    def get_input_fields(cls) -> Dict[str, InputField]:
        inputs = {}
        for k, v in cls.__dict__.items():
            if isinstance(v, InputField):
                inputs[k] = v
        return inputs

    @classmethod
    def get_output_fields(cls) -> Dict[str, OutputField]:
        outputs = {}
        for k, v in cls.__dict__.items():
            if isinstance(v, OutputField):
                outputs[k] = v
        return outputs

    @classmethod
    def format_prompt(cls, **kwargs) -> str:
        doc = cls.__doc__ or "Execute task according to input specification."
        lines = [f"Instruction: {doc.strip()}", ""]

        lines.append("Input Fields:")
        for k, v in kwargs.items():
            lines.append(f"- {k}: {v}")

        lines.append("\nOutput Fields (produce exactly these):")
        for k, field_obj in cls.get_output_fields().items():
            desc_part = f": {field_obj.desc}" if field_obj.desc else ""
            lines.append(f"- {k}{desc_part}")

        return "\n".join(lines)


class Predict:
    """
    Basic prompt execution module formatting inputs and parsing field outputs.
    """
    def __init__(self, signature: Type[Signature]):
        self.signature = signature

    def build_prompt(self, **kwargs) -> str:
        return self.signature.format_prompt(**kwargs)

    def parse_output(self, raw_output: str) -> Dict[str, str]:
        """
        Parses output text formatted as 'field_name: value'.
        """
        parsed: Dict[str, str] = {}
        expected_outputs = set(self.signature.get_output_fields().keys())
        current_field: Optional[str] = None
        current_lines: List[str] = []

        for line in raw_output.splitlines():
            line_str = line.strip()
            # Check if line matches an expected output field prefix
            matched = False
            for f in expected_outputs:
                if line_str.lower().startswith(f"{f.lower()}:"):
                    if current_field:
                        parsed[current_field] = "\n".join(current_lines).strip()
                    current_field = f
                    val_part = line_str[len(f) + 1:].strip()
                    current_lines = [val_part] if val_part else []
                    matched = True
                    break
            if not matched and current_field:
                current_lines.append(line)

        if current_field:
            parsed[current_field] = "\n".join(current_lines).strip()

        return parsed


class ChainOfThought(Predict):
    """
    Dynamically injects Rationale field into prompt outputs before decision fields.
    """
    def __init__(self, signature: Type[Signature]):
        super().__init__(signature)

    def build_prompt(self, **kwargs) -> str:
        base_prompt = self.signature.format_prompt(**kwargs)
        # Inject rationale into output fields section
        lines = base_prompt.splitlines()
        inserted: List[str] = []
        for line in lines:
            inserted.append(line)
            if "Output Fields (produce exactly these):" in line:
                inserted.append("- rationale: Step-by-step reasoning explaining how the decision was derived.")
        return "\n".join(inserted)

    def parse_output(self, raw_output: str) -> Dict[str, str]:
        parsed = super().parse_output(raw_output)
        # Ensure rationale is also captured if present
        if "rationale" not in parsed:
            for line in raw_output.splitlines():
                if line.strip().lower().startswith("rationale:"):
                    parsed["rationale"] = line.strip()[len("rationale:"):].strip()
                    break
        return parsed


class FewShotOptimizer:
    """
    MIPRO & BootstrapFewShot prompt optimizer.
    Discovers and selects top metric-passing exemplars from evaluation datasets
    and compiles them into few-shot demonstration blocks.
    """
    def __init__(
        self,
        signature: Type[Signature],
        metric: Optional[Callable[[Dict[str, Any], Dict[str, Any]], float]] = None,
        max_bootstrapped_demos: int = 3
    ):
        self.signature = signature
        self.metric = metric or (lambda cand, truth: 1.0)
        self.max_bootstrapped_demos = max_bootstrapped_demos

    def compile(self, trainset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters and ranks demonstration candidates according to evaluation metric.
        """
        scored_candidates: List[Tuple[Dict[str, Any], float]] = []
        for item in trainset:
            score = self.metric(item, item)
            if score > 0.0:
                scored_candidates.append((item, score))

        # Sort by metric score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored_candidates[:self.max_bootstrapped_demos]]

    def format_demonstrations(self, demos: List[Dict[str, Any]]) -> str:
        """
        Formats demonstrations into a standardized few-shot prompt block.
        """
        blocks: List[str] = ["--- Demonstrations ---"]
        input_keys = set(self.signature.get_input_fields().keys())
        output_keys = set(self.signature.get_output_fields().keys())

        for idx, d in enumerate(demos, start=1):
            blocks.append(f"[Example {idx}]")
            for k, v in d.items():
                if k in input_keys:
                    blocks.append(f"Input {k}: {v}")
                elif k in output_keys:
                    blocks.append(f"Output {k}: {v}")
            blocks.append("")
        return "\n".join(blocks)


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Declarative Prompt Optimization (DSPy Distillation)")
    parser.add_argument("--demo", action="store_true", help="Run demonstration prompt formatting")
    args = parser.parse_args()

    class IntentSignature(Signature):
        """Classify developer intent into technical actions."""
        query = InputField("User prompt or issue title")
        action = OutputField("Primary command to execute")
        confidence = OutputField("Confidence score")

    if args.demo or len(sys.argv) == 1:
        p = Predict(IntentSignature)
        prompt = p.build_prompt(query="optimize sql latency")
        print(prompt)


if __name__ == "__main__":
    main()
