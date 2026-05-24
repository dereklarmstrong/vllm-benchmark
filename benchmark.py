#!/usr/bin/env python3
"""vLLM Benchmark — Python implementation (stdlib only).

Usage:
    python3 benchmark.py [num_requests]

Configuration via environment variables or a .env file:
    VLLM_BASE_URL     — API endpoint  (default: http://localhost:8000/v1)
    VLLM_AUTH_TOKEN   — Bearer token  (default: none)
    VLLM_MODEL        — Model ID      (default: Qwen/Qwen2.5-7B-Instruct)
    VLLM_NUM_REQUESTS — Concurrency   (default: 3)
"""

import json
import os
import time
import sys
import argparse
import signal
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Defaults ─────────────────────────────────────────────────────────────

DEFAULTS = {
    "base_url": "http://localhost:8000/v1",
    "auth_token": "",
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "num_requests": 3,
}

# ── Prompts ──────────────────────────────────────────────────────────────

PROMPTS = [
    "Write a detailed 800 word science fiction story about a crew of astronauts who discover an ancient alien artifact on Mars that begins rewriting their memories.",
    "Write a detailed 800 word fantasy story about a young dragon rider who discovers they can communicate with ancient dragons and must unite the scattered dragon clans against a coming darkness.",
    "Write a detailed 800 word thriller story about a software engineer who realizes the AI system they built has been manipulating global financial markets for years without anyone noticing.",
    "Write a detailed 800 word mystery story about a detective who receives anonymous letters predicting crimes before they happen, only to realize the letters are in their own handwriting.",
    "Write a detailed 800 word horror story about a deep sea research team that discovers an underwater city where the buildings seem to rearrange themselves when no one is watching.",
    "Write a detailed 800 word adventure story about an archaeologist who finds a map leading to a library that contains every book that will ever be written.",
    "Write a detailed 800 word dystopian story about a society where dreams are taxed and a black market dream dealer discovers a dream that could topple the government.",
    "Write a detailed 800 word romance story set aboard a generation ship where two people from rival factions discover a secret that could save or destroy the entire vessel.",
]

LABELS = ["SCIENCE FICTION", "FANTASY", "THRILLER", "MYSTERY",
          "HORROR", "ADVENTURE", "DYSTOPIAN", "ROMANCE"]


# ── Colors ───────────────────────────────────────────────────────────────

C = dict(
    RED='\033[0;31m', GREEN='\033[0;32m', YELLOW='\033[0;33m',
    BLUE='\033[0;34m', MAGENTA='\033[0;35m', CYAN='\033[0;36m',
    WHITE='\033[0;37m', BOLD='\033[1m', RESET='\033[0m',
)


# ── Config ───────────────────────────────────────────────────────────────

def load_env(path=".env"):
    """Parse a simple dotenv file into os.environ."""
    if not os.path.isfile(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            os.environ[k] = v


load_env()

CFG = {
    "base_url": os.environ.get("VLLM_BASE_URL", DEFAULTS["base_url"]),
    "auth_token": os.environ.get("VLLM_AUTH_TOKEN", DEFAULTS["auth_token"]),
    "model": os.environ.get("VLLM_MODEL", DEFAULTS["model"]),
    "num_requests": int(os.environ.get("VLLM_NUM_REQUESTS", DEFAULTS["num_requests"])),
}


# ── Request ──────────────────────────────────────────────────────────────

def make_request(idx, prompt, cfg):
    url = f"{cfg['base_url']}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg["auth_token"]:
        headers["Authorization"] = f"Bearer {cfg['auth_token']}"
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1600,
    }
    start = time.time()
    try:
        req = Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(req, timeout=300) as resp:
            elapsed = time.time() - start
            data = json.loads(resp.read())
            return {"idx": idx, "ok": True, "data": data, "elapsed": elapsed}
    except HTTPError as e:
        elapsed = time.time() - start
        body = ""
        try:
            body = json.loads(e.read()).get("error", {}).get("message", e.reason)
        except Exception:
            body = e.reason
        return {"idx": idx, "ok": False, "error": f"HTTP {e.code}: {body}", "elapsed": elapsed}
    except URLError as e:
        elapsed = time.time() - start
        return {"idx": idx, "ok": False, "error": f"Connection failed: {e.reason}", "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        return {"idx": idx, "ok": False, "error": str(e), "elapsed": elapsed}


# ── Display ──────────────────────────────────────────────────────────────

def print_results(results, wall_time, num_req):
    results.sort(key=lambda r: r["idx"])
    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]

    if fail:
        print(f"\n{C['RED']}ERROR: {len(fail)} request(s) failed:{C['RESET']}")
        for r in fail:
            print(f"  Request #{r['idx']+1}: {r['error']}")
        sys.exit(1)

    story_names = [LABELS[i % len(LABELS)] for i in range(num_req)]

    # Header
    print(f"\n{C['BOLD']}{C['CYAN']}vLLM Benchmark Results{C['RESET']}")
    print(f"{C['BOLD']}{'─' * 69}{C['RESET']}")
    print(f"Server:                 {CFG['base_url']}")
    print(f"Model:                  {CFG['model']}")
    print(f"Concurrent Requests:    {num_req}")
    print(f"Time:                   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Per-request table
    print(f"\n{C['BOLD']}{C['BLUE']}Per-Request Metrics{C['RESET']}")
    print(f"{'─' * 65}")
    print(f"{'#':<4} {'Genre':<16} {'Prompt':>8} {'Completion':>12} {'Total':>10}")
    print(f"{'─' * 65}")
    for i, r in enumerate(ok):
        u = r["data"]["usage"]
        print(f"{i+1:<4} {story_names[i]:<16} {u['prompt_tokens']:>8} {u['completion_tokens']:>12} {u['total_tokens']:>10}")

    # Summary
    total_completion = sum(r["data"]["usage"]["completion_tokens"] for r in ok)
    total_tokens = sum(r["data"]["usage"]["total_tokens"] for r in ok)
    batched_tps = total_completion / wall_time if wall_time > 0 else 0
    avg_tps = batched_tps / num_req if num_req > 0 else 0

    if batched_tps >= 100: rating, rc = "EXCELLENT", C["GREEN"]
    elif batched_tps >= 50: rating, rc = "GOOD", C["CYAN"]
    elif batched_tps >= 20: rating, rc = "FAIR", C["YELLOW"]
    else: rating, rc = "SLOW", C["RED"]

    print(f"\n{C['BOLD']}{C['GREEN']}Performance Summary{C['RESET']}")
    print(f"{'─' * 60}")
    print(f"Wall Time:            {wall_time:.3f}s")
    print(f"Total Completion:     {total_completion:,} tokens")
    print(f"Total Tokens:         {total_tokens:,} tokens")
    print(f"Batched Throughput:   {batched_tps:.1f} tokens/sec")
    print(f"Avg Per-Request:      {avg_tps:.1f} tokens/sec")

    # Bar
    max_bw, max_tps = 50, 150
    bw = min(int((batched_tps / max_tps) * max_bw), max_bw)
    bar = '█' * bw
    scale = f"  {C['CYAN']}0{'─' * 14}{C['YELLOW']}{'─' * 14}{C['BLUE']}{'─' * 14}{C['MAGENTA']}{'─' * 4}{C['GREEN']}{'─' * 4}{C['WHITE']}{max_tps}{C['RESET']}"
    val = f"  {C['CYAN']}│{C['RESET']} {bar:<{max_bw}} {batched_tps:.1f} tok/s{C['RESET']}"
    val = val + " " * max(len(scale) - len(val), 0)
    print(f"\n{C['BOLD']}{C['GREEN']}Throughput Visualization{C['RESET']}")
    print(scale)
    print(val)

# Content preview removed to avoid leaking generated output

    # Health + rating
    print(f"\n{C['BOLD']}{C['CYAN']}Health Check & Rating{C['RESET']}")
    print(f"{'─' * 60}")
    for label, check in [
        ("All requests completed", all(r["data"].get("choices") for r in ok)),
        ("No errors in responses", all("error" not in r["data"] for r in ok)),
        ("Valid token counts", all(r["data"]["usage"]["completion_tokens"] > 0 for r in ok)),
    ]:
        sym = f"{C['GREEN']}✓{C['RESET']}" if check else f"{C['RED']}✗{C['RESET']}"
        print(f"  {sym}  {label}")

    print(f"\n{C['BOLD']}{C['CYAN']}Overall Performance Rating:{C['RESET']} {rc}{C['BOLD']}{rating}{C['RESET']}")
    print(f"\n{C['BOLD']}{C['CYAN']}Performance Tips:{C['RESET']}")
    if batched_tps < 20:
        print("  • Increase GPU memory utilization flag on server")
        print("  • Reduce max_tokens in your requests")
        print("  • Check for network latency between client and server")
    elif batched_tps < 50:
        print("  • Acceptable for most use cases")
        print("  • Try higher concurrency to push throughput")
    else:
        print("  • Excellent performance — system is well-optimized")
        print("  • Try higher concurrency to find your server's limit")

    print(f"\n{C['GREEN']}✓ Benchmark completed in {wall_time:.3f}s{C['RESET']}\n")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark vLLM server throughput")
    parser.add_argument("num_requests", nargs="?", type=int, default=None,
                        help="Number of concurrent requests (default: from config or 3)")
    args = parser.parse_args()

    num_req = args.num_requests or CFG["num_requests"]
    prompts = [PROMPTS[i % len(PROMPTS)] for i in range(num_req)]

    start = time.time()
    with ThreadPoolExecutor(max_workers=num_req) as pool:
        futs = {pool.submit(make_request, i, p, CFG): i for i, p in enumerate(prompts)}
        results = [f.result() for f in as_completed(futs)]
    wall = time.time() - start

    print_results(results, wall, num_req)


if __name__ == "__main__":
    main()
