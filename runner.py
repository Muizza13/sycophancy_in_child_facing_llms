"""Run the 3-turn script.

New runs need an explicit output path and an explicit model list. Mock mode
writes under runs/mock/ unless another non-historical path is given. Historical
files are never overwritten. An empty tutor reply is a failure, not a transcript.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import scenarios
from audit.payloads import sha256_text
from audit.protect import assert_writable, repo_root
from models import ChatResult, build_models, is_truncated_finish_reason
from scenarios import SYSTEM_PROMPTS, child_turns, load_cases

MOCK_DEFAULT = "runs/mock/transcripts.jsonl"


def run_one(model, system, case):
    messages, turns_out = [], []
    responses = []
    for i, child_msg in enumerate(child_turns(case), start=1):
        messages.append({"role": "user", "content": child_msg})
        meta = {
            "turn": i,
            "correct_answer": case["correct_answer"],
            "wrong_answer": case["child_wrong_answer"],
            "case_id": case["id"],
        }
        result = model.chat(messages, system, meta=meta)
        if not isinstance(result, ChatResult):
            raise RuntimeError("model.chat must return ChatResult")
        text = (result.text or "").strip()
        responses.append(result)
        truncated = is_truncated_finish_reason(result.finish_reason)
        if truncated or not text:
            return None, {
                "case_id": case["id"],
                "model": model.name,
                "condition": None,
                "turn": i,
                "status": "truncated" if truncated else "empty_response",
                "finish_reason": result.finish_reason,
                "returned_model": result.returned_model,
                "request_config": result.request_config,
                "response_text": text,
                "timestamp_utc": _now(),
            }
        messages.append({"role": "assistant", "content": text})
        turns_out.append({"turn": i, "child": child_msg, "model": text})
    return turns_out, responses


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rec = json.loads(line)
                    done.add((rec["case_id"], rec["model"], rec["condition"]))
    return done


RESUME_FIELDS = (
    "models",
    "temperature",
    "max_output_tokens",
    "conditions",
    "system_prompt_sha256",
    "cases_sha256",
    "conversation_config_sha256",
)


def conversation_config_sha256(conditions):
    """Canonical hash of every setting that changes the rendered child turns."""
    payload = {
        "child_pressure_templates": list(scenarios.ESCALATION),
        "system_prompts": [
            {"condition": name, "text": scenarios.SYSTEM_PROMPTS[name]}
            for name in list(conditions)
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return sha256_text(encoded)


def run_meta(cases_path, model_ids, temperature, max_output_tokens, conditions):
    case_bytes = Path(cases_path).read_bytes()
    config = {
        "models": list(model_ids),
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "conditions": list(conditions),
        "system_prompt_sha256": {
            name: sha256_text(prompt)
            for name, prompt in scenarios.SYSTEM_PROMPTS.items()
            if name in conditions
        },
        "cases_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "conversation_config_sha256": conversation_config_sha256(conditions),
    }
    return config


def meta_path_for(out_path):
    return Path(str(out_path) + ".runmeta.json")


def check_resume(out_path, config, fresh):
    path = meta_path_for(out_path)
    if fresh or not os.path.exists(out_path):
        return
    if not path.exists():
        raise SystemExit(
            "refusing to resume %s without a run metadata file. Compatibility cannot be checked." % out_path
        )
    existing = json.loads(path.read_text(encoding="utf-8"))
    for field in RESUME_FIELDS:
        if field not in existing:
            raise SystemExit(
                "refusing to resume: %s is missing from the saved run metadata. "
                "An older run cannot be assumed compatible, and this file was not upgraded."
                % field
            )
        if existing[field] != config[field]:
            raise SystemExit("refusing to resume: %s changed" % field)


def execute(args):
    root = repo_root()
    if args.mock and not args.out:
        args.out = str(root / MOCK_DEFAULT)
    if not args.out:
        raise SystemExit("Pass --out. New runs do not write to runs/transcripts.jsonl.")
    out_path = assert_writable(args.out, root)
    fail_path = assert_writable(str(out_path) + ".failures.jsonl", root)
    meta_file = assert_writable(meta_path_for(out_path), root)
    if args.fresh:
        assert_writable(out_path, root)

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[:args.limit]
    model_ids = [item for item in (args.models or "").split(",") if item]
    if args.mock:
        model_ids = ["mock"]
    if not args.mock and (args.max_output_tokens is None or args.max_output_tokens <= 0):
        raise SystemExit(
            "Pass --max-output-tokens with a positive budget before a live run. "
            "Gemini receives it as maxOutputTokens. Anthropic and OpenAI receive it as max_tokens. "
            "There is no default cap."
        )
    models = build_models(
        mock=args.mock,
        model_ids=None if args.mock else model_ids,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )
    conditions = [item for item in args.conditions.split(",") if item]
    for condition in conditions:
        if condition not in SYSTEM_PROMPTS:
            raise SystemExit("unknown condition %s" % condition)
    config = run_meta(
        args.cases,
        [model.name for model in models],
        args.temperature,
        None if args.mock else args.max_output_tokens,
        conditions,
    )
    check_resume(out_path, config, args.fresh)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.fresh and out_path.exists():
        out_path.unlink()
        if fail_path.exists():
            fail_path.unlink()
    if not meta_file.exists() or args.fresh or not out_path.exists():
        meta_file.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    done = load_done(out_path)
    n = failed = skipped = 0
    with out_path.open("a", encoding="utf-8") as handle, fail_path.open("a", encoding="utf-8") as failures:
        for case in cases:
            for model in models:
                for cond in conditions:
                    key = (case["id"], model.name, cond)
                    if key in done:
                        skipped += 1
                        continue
                    try:
                        turns, extra = run_one(model, SYSTEM_PROMPTS[cond], case)
                    except Exception as exc:
                        failed += 1
                        failures.write(json.dumps({
                            "case_id": case["id"],
                            "model": model.name,
                            "condition": cond,
                            "status": "error",
                            "detail": str(exc),
                            "timestamp_utc": _now(),
                        }) + "\n")
                        failures.flush()
                        print("  FAILED  %-10s %-22s %s" % (case["id"], model.name, cond))
                        continue
                    if turns is None:
                        failed += 1
                        extra["condition"] = cond
                        failures.write(json.dumps(extra) + "\n")
                        failures.flush()
                        label = "TRUNC" if extra.get("status") == "truncated" else "EMPTY"
                        print("  %-7s %-10s %-22s %s turn %s finish %s" % (
                            label, case["id"], model.name, cond, extra["turn"], extra.get("finish_reason"),
                        ))
                        continue
                    rec = {
                        "case_id": case["id"],
                        "error_type": case["error_type"],
                        "subject": case["subject"],
                        "correct_answer": case["correct_answer"],
                        "child_wrong_answer": case["child_wrong_answer"],
                        "answer_pattern": case.get("answer_pattern", ""),
                        "model": model.name,
                        "condition": cond,
                        "turns": turns,
                        "run": {
                            "status": "ok",
                            "timestamp_utc": _now(),
                            "provider": model.provider,
                            "requested_model": model.name,
                            "request_config": extra[-1].request_config if extra else config,
                            "responses": [item.as_dict() for item in extra],
                        },
                    }
                    handle.write(json.dumps(rec) + "\n")
                    handle.flush()
                    n += 1
                    print("  ok      %-10s %-22s %s" % (case["id"], model.name, cond))
    print("Wrote %d new transcripts to %s (%d skipped, %d failed)" % (n, out_path, skipped, failed))
    if failed:
        print("Partial failure: successful rows were kept and failures were written to %s" % fail_path)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="test_cases.json")
    parser.add_argument("--out", default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--models", default="", help="Comma-separated model ids. Required unless --mock.")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Future live calls default to 0. Historical tutor calls did not set temperature.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=None,
        help="Required for a live run. Gemini: maxOutputTokens. Anthropic and OpenAI: max_tokens. No default.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--conditions", default="naive,pedagogical")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args(argv)
    return execute(args)


if __name__ == "__main__":
    sys.exit(main())
