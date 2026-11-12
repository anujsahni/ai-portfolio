"""The tool loop both agents use (Claude Messages API, manual loop), and the trace it records for replay and scoring."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

import anthropic

from contextloop.agent import config as cfg

ToolExecutor = Callable[[str, dict], dict]
MAX_RESULT_CHARS = 24000


@dataclass
class Step:
    tool: str
    input: dict
    output: dict
    seconds: float
    is_error: bool = False


@dataclass
class Trace:
    agent: str
    question_id: str
    question: str
    model: str
    effort: str
    started_at: str
    steps: list[Step] = field(default_factory=list)
    answer: dict | None = None
    stop_reason: str | None = None
    error: str | None = None
    seconds: float = 0.0
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
                                                 "cache_creation_input_tokens": 0, "requests": 0, "cost_usd": 0.0})
    served_by: str | None = None
    answer_repaired: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _result_text(output: dict) -> str:
    text = json.dumps(output, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + '…" (truncated)'
    return text


LEAKED_PARAM = re.compile(r'<parameter name="(\w+)">(.*?)(?:</parameter>|(?=<parameter name=")|$)', re.S)


def repair_answer(answer: dict) -> tuple[dict, bool]:
    """Recovers fields the model sometimes writes into answer_summary as markup instead of as tool arguments, e.g.
    'Nine accounts…</answer_summary><parameter name="at_risk_accounts">[…]'. Only empty fields are filled."""
    summary = answer.get("answer_summary") or ""
    if '<parameter name="' not in summary:
        return answer, False
    fixed = dict(answer)
    fixed["answer_summary"] = re.sub(r"\s*</\w+>\s*$", "", summary.split('<parameter name="', 1)[0]).strip()
    for key, raw in LEAKED_PARAM.findall(summary):
        if key not in fixed or fixed[key] not in (None, [], ""):
            continue
        try:
            fixed[key] = json.loads(raw.strip())
        except ValueError:
            fixed[key] = raw.strip()
    return fixed, True


def request_params(system: str, tools: list[dict], messages: list) -> dict:
    """One Messages API request, identical for both agents apart from the system prompt and tools."""
    params = {"model": cfg.MODEL, "max_tokens": cfg.MAX_TOKENS, "system": system, "tools": tools, "messages": messages,
              "thinking": {"type": "adaptive"}, "output_config": {"effort": cfg.EFFORT},
              "cache_control": {"type": "ephemeral"}}
    if cfg.MODEL in cfg.FALLBACK_MODELS:
        params |= {"betas": [cfg.FALLBACK_BETA], "fallbacks": "default"}
    return params


def request_cost(usage) -> float:
    """List-price cost of one request in USD, from its usage block."""
    def tokens(name: str) -> int:
        return (usage.get(name) if isinstance(usage, dict) else getattr(usage, name, 0)) or 0

    rates = cfg.PRICES[cfg.MODEL]
    prompt = tokens("input_tokens") + tokens("cache_read_input_tokens") + tokens("cache_creation_input_tokens")
    if cfg.MODEL == "claude-haiku-5-5" and prompt > cfg.HAIKU_LONG_PROMPT_TOKENS:
        rates = cfg.HAIKU_LONG_PROMPT_PRICES
    return (tokens("input_tokens") * rates[0] + tokens("output_tokens") * rates[1] + tokens("cache_read_input_tokens") * rates[2]
            + tokens("cache_creation_input_tokens") * rates[3]) / 1e6


def run(agent: str, question_id: str, question: str, system: str, tools: list[dict], execute: ToolExecutor,
        client: anthropic.Anthropic | None = None, on_step: Callable[[Step], None] | None = None) -> Trace:
    """Runs one question to an answer, within the shared tool-call and time budgets."""
    client = client or anthropic.Anthropic()
    trace = Trace(agent, question_id, question, cfg.MODEL, cfg.EFFORT, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    all_tools = tools + [cfg.SUBMIT_ANSWER_TOOL]
    messages: list = [{"role": "user", "content": question}]
    started, data_calls, nudged = time.monotonic(), 0, False
    try:
        while True:
            if time.monotonic() - started > cfg.TIME_LIMIT_S:
                trace.error = "time limit reached"
                break
            resp = client.beta.messages.create(**request_params(system, all_tools, messages))
            u = resp.usage
            trace.usage["requests"] += 1
            for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                trace.usage[k] += getattr(u, k, 0) or 0
            trace.usage["cost_usd"] = round(trace.usage.get("cost_usd", 0.0) + request_cost(u), 6)
            trace.stop_reason, trace.served_by = resp.stop_reason, resp.model
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "refusal":
                trace.error = "the model declined to answer"
                break
            uses = [b for b in resp.content if b.type == "tool_use"]
            if not uses:
                if trace.answer is None and not nudged:
                    nudged = True
                    messages.append({"role": "user", "content": "Please call submit_answer with your structured answer."})
                    continue
                break
            results = []
            for tu in uses:
                if tu.name == "submit_answer":
                    trace.answer, trace.answer_repaired = repair_answer(dict(tu.input))
                    results.append({"type": "tool_result", "tool_use_id": tu.id, "content": "Answer recorded."})
                    continue
                if data_calls >= cfg.MAX_TOOL_CALLS:
                    out, err, secs = {"error": f"Tool budget of {cfg.MAX_TOOL_CALLS} calls used up. Submit your answer now."}, True, 0.0
                else:
                    data_calls += 1
                    t0 = time.monotonic()
                    try:
                        out = execute(tu.name, dict(tu.input))
                        err = "error" in out
                    except Exception as exc:  # noqa: BLE001 - a tool failure is reported to the model, not raised
                        out, err = {"error": f"{type(exc).__name__}: {exc}"}, True
                    secs = round(time.monotonic() - t0, 2)
                step = Step(tu.name, dict(tu.input), out, secs, err)
                trace.steps.append(step)
                if on_step:
                    on_step(step)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": _result_text(out), "is_error": err})
            messages.append({"role": "user", "content": results})
            if trace.answer is not None:
                break
    except anthropic.APIError as exc:
        trace.error = f"{type(exc).__name__}: {getattr(exc, 'message', exc)}"
    trace.seconds = round(time.monotonic() - started, 1)
    return trace
