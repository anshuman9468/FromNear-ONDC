#!/usr/bin/env python3
"""Extract and normalize failed assertions from a Workbench HTML report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


INDEX_RE = re.compile(r"\[(?:\\?\d+)\]")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T[^ '\"]+")


def normalize(value: str) -> str:
    value = value or ""
    value = INDEX_RE.sub("[*]", value)
    value = UUID_RE.sub("<uuid>", value)
    value = TIMESTAMP_RE.sub("<timestamp>", value)
    return value


def walk(node: object, flow: str = ""):
    if not isinstance(node, dict):
        return
    for test in node.get("tests", []):
        yield test, flow
    for suite in node.get("suites", []):
        title = suite.get("title", "")
        next_flow = f"{flow} / {title}" if flow else title
        yield from walk(suite, next_flow)


def parse_report(path: Path) -> dict:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    raw = soup.body.get("data-raw")
    if not raw:
        raise ValueError(f"{path} does not contain Workbench data-raw report data")
    report = json.loads(raw)
    failures = []
    for result in report.get("results", []):
        for test, flow in walk(result):
            if not test.get("fail"):
                continue
            error = test.get("err") or {}
            message = error.get("message", "") if isinstance(error, dict) else str(error)
            normalized_title = normalize(test.get("fullTitle", ""))
            normalized_message = normalize(message)
            lower = f"{normalized_title} {normalized_message}".lower()
            if "retail_bap_" in lower or "request verification" in lower and "bpp" not in lower:
                owner = "Workbench/BAP input"
            elif "retail_bpp_" in lower or "on_search" in lower or "on_select" in lower:
                owner = "Seller BPP or callback"
            else:
                owner = "Needs triage"
            failures.append({
                "flow": flow,
                "api": next((part for part in flow.split(" / ") if part.startswith(("on_", "select", "init", "confirm", "update", "cancel", "status", "track"))), "unknown"),
                "assertion": normalized_title,
                "payload_path": normalized_message,
                "expected": "",
                "actual": normalized_message,
                "request_or_callback": "callback" if "retail_bpp_" in lower else "request",
                "root_cause_group": owner,
                "owner": owner,
            })
    return {
        "source": str(path),
        "stats": report.get("stats", {}),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    parsed = [parse_report(report) for report in args.reports]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
