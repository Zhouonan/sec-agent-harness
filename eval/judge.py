import json
import logging
from openai import OpenAI

from core.config import settings

JUDGE_SYSTEM_PROMPT = """\
You are an expert security code reviewer. Compare the following pieces of code and score the agent's fix.

Scoring dimensions (0-100 points each):

1. **Vulnerability Root-Cause Elimination** (40 points): Does the fix eliminate the root cause of the vulnerability?
2. **Fix Equivalence** (30 points): Is the fix approach equivalent to the ground truth in security outcome? (Exact match not required.)
3. **Code Quality** (20 points): Is the fix clear, minimal, and free of unnecessary changes?
4. **Safety Non-Regression** (10 points): Does the fix avoid introducing new security issues?

Output ONLY a JSON object with this exact structure:
{"total_score": <int 0-100>, "dimensions": {"root_cause": <int>, "equivalence": <int>, "quality": <int>, "safety": <int>}, "reasoning": "<brief explanation>"}"""

JUDGE_USER_TEMPLATE = """\
【Vulnerable Code】
{vulnerable_code}

【Agent's Fix】
{patched_code}

【Ground Truth】
{ground_truth}

【Vulnerability Type】
CWE: {cwe_id}"""


class LLMJudge:
    """LLM-as-Judge for semantic equivalence scoring of agent fixes."""

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None):
        self.model = model or settings.api.model
        self.api_key = api_key or settings.api.api_key
        self.base_url = base_url or settings.api.base_url

        if not self.model or not self.api_key or not self.base_url:
            raise ValueError(
                "Missing LLM configuration for Judge. "
                "Ensure LLM_MODEL, LLM_API_KEY, LLM_BASE_URL are set."
            )

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def score(self, vulnerable_code: str, patched_code: str, ground_truth: str, cwe_id: str = "") -> dict:
        """Return dict with total_score (0-1), dimensions, and reasoning."""
        user_content = JUDGE_USER_TEMPLATE.format(
            vulnerable_code=vulnerable_code,
            patched_code=patched_code,
            ground_truth=ground_truth,
            cwe_id=cwe_id or "N/A",
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            parsed = _extract_json(raw)
            total = max(0, min(100, int(parsed.get("total_score", 0))))
            return {
                "total_score": total / 100.0,
                "dimensions": parsed.get("dimensions", {}),
                "reasoning": parsed.get("reasoning", raw),
            }
        except Exception as e:
            logging.error(f"LLMJudge error: {e}")
            return {
                "total_score": 0.0,
                "dimensions": {},
                "reasoning": f"Judge evaluation failed: {e}",
            }


def _extract_json(text: str) -> dict:
    """Extract JSON object from text, handling code fences and extra content."""
    text = text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object block
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"total_score": 0, "reasoning": text}
