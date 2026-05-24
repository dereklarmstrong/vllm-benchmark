#!/bin/bash

# vLLM Benchmark - Quick concurrent throughput test
# Usage: ./bench.sh [num_requests]
#
# Configuration:
#   Copy .env.example to .env and edit, or set env vars directly:
#     VLLM_BASE_URL, VLLM_AUTH_TOKEN, VLLM_MODEL, VLLM_NUM_REQUESTS

set -euo pipefail

# Load .env if present
[ -f .env ] && set -a && source .env && set +a

# Config
BASE_URL="${VLLM_BASE_URL:-http://localhost:8000/v1}"
AUTH_TOKEN="${VLLM_AUTH_TOKEN:-}"
MODEL="${VLLM_MODEL:-Qwen/Qwen2.5-7B-Instruct}"
NUM_REQUESTS="${1:-${VLLM_NUM_REQUESTS:-3}}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
BLUE='\033[0;34m'; MAGENTA='\033[0;35m'; CYAN='\033[0;36m'
WHITE='\033[0;37m'; BOLD='\033[1m'; RESET='\033[0m'

# Prompts
PROMPTS=(
  "Write a detailed 800 word science fiction story about a crew of astronauts who discover an ancient alien artifact on Mars that begins rewriting their memories."
  "Write a detailed 800 word fantasy story about a young dragon rider who discovers they can communicate with ancient dragons and must unite the scattered dragon clans against a coming darkness."
  "Write a detailed 800 word thriller story about a software engineer who realizes the AI system they built has been manipulating global financial markets for years without anyone noticing."
  "Write a detailed 800 word mystery story about a detective who receives anonymous letters predicting crimes before they happen, only to realize the letters are in their own handwriting."
  "Write a detailed 800 word horror story about a deep sea research team that discovers an underwater city where the buildings seem to rearrange themselves when no one is watching."
  "Write a detailed 800 word adventure story about an archaeologist who finds a map leading to a library that contains every book that will ever be written."
  "Write a detailed 800 word dystopian story about a society where dreams are taxed and a black market dream dealer discovers a dream that could topple the government."
  "Write a detailed 800 word romance story set aboard a generation ship where two people from rival factions discover a secret that could save or destroy the entire vessel."
)
PROMPT_COUNT=${#PROMPTS[@]}
STORY_LABELS=("SCIENCE FICTION" "FANTASY" "THRILLER" "MYSTERY" "HORROR" "ADVENTURE" "DYSTOPIAN" "ROMANCE")

# Clean old responses
rm -f /tmp/vllm_response_*.json

# Auth header
AUTH_HEADER=""
[ -n "$AUTH_TOKEN" ] && AUTH_HEADER="-H \"Authorization: Bearer ${AUTH_TOKEN}\""

# Start timing
START=$(date +%s%N)

# Fire concurrent requests
for ((i=1; i<=NUM_REQUESTS; i++)); do
  PROMPT_IDX=$(( (i - 1) % PROMPT_COUNT ))
  CURL_ARGS=(
    -s --connect-timeout 10 --max-time 300
    "${BASE_URL}/chat/completions"
    -H "Content-Type: application/json"
    -d "{\"model\": \"${MODEL}\", \"messages\": [{\"role\": \"user\", \"content\": \"${PROMPTS[$PROMPT_IDX]}\"}], \"max_tokens\": 1600}"
    -o "/tmp/vllm_response_${i}.json"
  )
  if [ -n "$AUTH_TOKEN" ]; then
    CURL_ARGS+=("-H" "Authorization: Bearer ${AUTH_TOKEN}")
  fi
  curl "${CURL_ARGS[@]}" &
done

wait

# Check responses
RESPONSE_FILES_OK=true
for ((i=1; i<=NUM_REQUESTS; i++)); do
  if [ ! -f "/tmp/vllm_response_${i}.json" ]; then
    echo -e "${RED}ERROR: Failed to retrieve response ${i}. Server at ${BASE_URL} may be unreachable.${RESET}" >&2
    RESPONSE_FILES_OK=false
  fi
done

if [ "$RESPONSE_FILES_OK" = false ]; then
  echo -e "${YELLOW}Ensure vLLM is running and accessible at ${BASE_URL}${RESET}" >&2
  exit 1
fi
END=$(date +%s%N)

# Print header
echo ""
echo -e "${BOLD}${CYAN}vLLM Benchmark Results${RESET}"
echo -e "${BOLD}───────────────────────────────────────────────────────────────────────────────${RESET}"
echo -e "Server:                 ${BASE_URL}"
echo -e "Model:                  ${MODEL}"
echo -e "Concurrent Requests:    ${NUM_REQUESTS}"
echo -e "Time:                   $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Process results
export BENCHMARK_START=$START BENCHMARK_END=$END BENCHMARK_NUM_REQUESTS=$NUM_REQUESTS
python3 - <<'PYEOF'
import json, os, sys

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
BLUE='\033[0;34m'; MAGENTA='\033[0;35m'; CYAN='\033[0;36m'
WHITE='\033[0;37m'; BOLD='\033[1m'; RESET='\033[0m'

START_NS = int(os.environ['BENCHMARK_START'])
END_NS = int(os.environ['BENCHMARK_END'])
NUM_REQUESTS = int(os.environ['BENCHMARK_NUM_REQUESTS'])

ALL_LABELS = ["SCIENCE FICTION", "FANTASY", "THRILLER", "MYSTERY", "HORROR", "ADVENTURE", "DYSTOPIAN", "ROMANCE"]

responses = []
for i in range(1, NUM_REQUESTS + 1):
    try:
        with open(f'/tmp/vllm_response_{i}.json') as f:
            content = f.read()
        if not content or content.startswith('<'):
            print(f"\n{RED}ERROR: Response #{i} is not JSON (got HTML?). Check server is reachable.{RESET}")
            sys.exit(1)
        r = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"\n{RED}ERROR: Response #{i} contains invalid JSON: {e}{RESET}")
        print(f"{YELLOW}Check that the server returned a valid completion.{RESET}")
        sys.exit(1)
    if 'error' in r:
        print(f"\n{RED}API Error: {r['error'].get('message', 'Unknown')}{RESET}"); sys.exit(1)
    if not r.get('choices') or not r.get('usage'):
        print(f"\n{RED}Invalid response #{i} — missing choices or usage fields{RESET}"); sys.exit(1)
    responses.append(r)

story_names = [ALL_LABELS[i % len(ALL_LABELS)] for i in range(NUM_REQUESTS)]

print(f"\n{BOLD}{BLUE}Per-Request Metrics{RESET}")
print(f"{'─' * 65}")
print(f"{'#':<4} {'Genre':<16} {'Prompt':>8} {'Completion':>12} {'Total':>10}")
print(f"{'─' * 65}")
for i, r in enumerate(responses):
    u = r['usage']
    print(f"{i+1:<4} {story_names[i]:<16} {u['prompt_tokens']:>8} {u['completion_tokens']:>12} {u['total_tokens']:>10}")

elapsed = (END_NS - START_NS) / 1e9
total_completion = sum(r['usage']['completion_tokens'] for r in responses)
total_tokens = sum(r['usage']['total_tokens'] for r in responses)
batched_tps = total_completion / elapsed if elapsed > 0 else 0
avg_tps = batched_tps / NUM_REQUESTS if NUM_REQUESTS > 0 else 0

if batched_tps >= 100: rating, color = "EXCELLENT", GREEN
elif batched_tps >= 50: rating, color = "GOOD", CYAN
elif batched_tps >= 20: rating, color = "FAIR", YELLOW
else: rating, color = "SLOW", RED

print(f"\n{BOLD}{GREEN}Performance Summary{RESET}")
print(f"{'─' * 60}")
print(f"Wall Time:            {elapsed:.3f}s")
print(f"Total Completion:     {total_completion:,} tokens")
print(f"Total Tokens:         {total_tokens:,} tokens")
print(f"Batched Throughput:   {batched_tps:.1f} tokens/sec")
print(f"Avg Per-Request:      {avg_tps:.1f} tokens/sec")

print(f"\n{BOLD}{GREEN}Throughput Visualization{RESET}")
max_bw, max_tps = 50, 150
bw = min(int((batched_tps / max_tps) * max_bw), max_bw)
bar = '█' * bw
scale = f"  {CYAN}0{'─' * 14}{YELLOW}{'─' * 14}{BLUE}{'─' * 14}{MAGENTA}{'─' * 4}{GREEN}{'─' * 4}{WHITE}{max_tps}{RESET}"
val = f"  {CYAN}│{RESET} {bar:<{max_bw}} {batched_tps:.1f} tok/s{RESET}"
# Pad to match scale length
padding_needed = len(scale) - len(val)
val = val + " " * max(padding_needed, 0)
print(scale)
print(val)

print(f"\n{BOLD}{CYAN}Health Check & Rating{RESET}")
print(f"{'─' * 60}")
checks = [
    ("All requests completed", all(r.get('choices') for r in responses)),
    ("No errors in responses", all('error' not in r for r in responses)),
    ("Valid token counts", all(r['usage']['completion_tokens'] > 0 for r in responses)),
]
for label, ok in checks:
    sym, col = (f"{GREEN}✓{RESET}", GREEN) if ok else (f"{RED}✗{RESET}", RED)
    print(f"  {sym}  {label}")

print(f"\n{BOLD}{CYAN}Overall Performance Rating:{RESET} {color}{BOLD}{rating}{RESET}")
print(f"\n{BOLD}{CYAN}Performance Tips:{RESET}")
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

print(f"\n{GREEN}✓ Benchmark completed in {elapsed:.3f}s{RESET}\n")
PYEOF

# Cleanup
rm -f /tmp/vllm_response_*.json
exit $?
