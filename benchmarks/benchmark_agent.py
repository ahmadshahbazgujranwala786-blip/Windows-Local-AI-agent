from __future__ import annotations

import argparse
import json
import time

import requests


TASKS = [
    "Say hello to Ahmad",
    "Open Notepad and type Ahmad",
    "Open Microsoft Edge and search YouTube",
    "List the files in my Pictures folder",
    "What is my current RAM usage?",
]


def run(base_url: str, repeats: int, timeout: float) -> None:
    results: list[dict] = []
    for task in TASKS:
        for repeat in range(repeats):
            started = time.perf_counter()
            try:
                response = requests.post(
                    f"{base_url}/execute/text",
                    json={"text": task, "language": "en"},
                    timeout=timeout,
                )
                payload = response.json()
                results.append({
                    "task": task,
                    "repeat": repeat + 1,
                    "http_status": response.status_code,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "request_elapsed_ms": payload.get("request_elapsed_ms"),
                    "timings": payload.get("timings", []),
                    "error": payload.get("detail"),
                })
            except Exception as exc:
                results.append({"task": task, "repeat": repeat + 1, "error": str(exc)})
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
            with open("benchmark-results.json", "w", encoding="utf-8") as output:
                json.dump(results, output, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30)
    arguments = parser.parse_args()
    run(arguments.base_url, arguments.repeats, arguments.timeout)