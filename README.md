# vLLM Benchmark

Lightweight, zero-dependency benchmark tool for measuring vLLM server throughput under concurrent load.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

Sends concurrent requests to a vLLM server and reports per-request and aggregate throughput metrics — tokens/second, wall time, token counts — with a visual performance rating.

**Zero dependencies.** The bash script needs `curl` and `python3` (stdlib). The Python script needs only `python3`.

## Quick Start

```bash
git clone https://github.com/yourusername/vllm-benchmark.git
cd vllm-benchmark
cp .env.example .env
# Edit .env with your server details
```

Or just set environment variables:

```bash
export VLLM_BASE_URL="http://localhost:8000/v1"
export VLLM_MODEL="Qwen/Qwen2.5-7B-Instruct"
./bench.sh
```

## Usage

### Bash (shell + python3 stdlib)

```bash
# Default: 3 concurrent requests
./bench.sh

# Custom concurrency
./bench.sh 8
```

### Python (stdlib only, no external packages)

```bash
# Default: 3 concurrent requests
python3 benchmark.py

# Custom concurrency
python3 benchmark.py 8
```

## Configuration

| Env Variable | Description | Default |
|---|---|---|
| `VLLM_BASE_URL` | vLLM API endpoint | `http://localhost:8000/v1` |
| `VLLM_AUTH_TOKEN` | Bearer token (leave empty if none) | *(empty)* |
| `VLLM_MODEL` | Hugging Face model ID | `Qwen/Qwen2.5-7B-Instruct` |
| `VLLM_NUM_REQUESTS` | Concurrent requests | `3` |

## Example Output

```
vLLM Benchmark Results
───────────────────────────────────────────────────────────────────────────────
Server:                 http://localhost:8000/v1
Model:                  Qwen/Qwen2.5-7B-Instruct
Concurrent Requests:    2
Time:                   2025-01-15 14:32:10

Per-Request Metrics
────────────────────────────────────────────────────────────────────────────────
#    Genre            Prompt   Completion      Total
────────────────────────────────────────────────────────────────────────────────
1    SCIENCE FICTION      41         2000       2041
2    FANTASY              46         2000       2046

Performance Summary
────────────────────────────────────────────────────────────────────
Wall Time:            32.593s
Total Completion:     4,000 tokens
Total Tokens:         4,087 tokens
Batched Throughput:   122.7 tokens/sec
Avg Per-Request:      61.4 tokens/sec

Overall Performance Rating: EXCELLENT
```

### Performance Ratings

| Rating | Throughput | Meaning |
|---|---|---|
| **EXCELLENT** | >= 100 tok/s | Well-optimized, ready for production |
| **GOOD** | 50-99 tok/s | Solid performance |
| **FAIR** | 20-49 tok/s | Acceptable, room for tuning |
| **SLOW** | < 20 tok/s | Needs optimization |

## What the Test Does

- Sends `N` concurrent requests using varied creative-writing prompts (not biased toward any single domain)
- Each request asks for ~1000 words of generated text (max 2000 tokens)
- Measures wall-clock time for the entire batch to complete
- Reports both aggregate throughput and per-request average
- Validates response structure and exits on failures

## Interpreting Results

**Batched Throughput** — total completion tokens across all requests divided by wall time. This is your server's aggregate throughput when handling concurrent requests.

**Avg Per-Request** — batched throughput divided by number of requests. This shows the effective throughput per individual request.

**Increasing concurrency doesn't always increase throughput.** vLLM's continuous batching has a sweet spot where adding more requests saturates the GPU. Beyond that you get queue latency, not more throughput. Use this tool to find that ceiling.

## Troubleshooting

**"Server unreachable" or empty responses:**
```bash
# Verify server is running
curl http://localhost:8000/v1/models

# Check your BASE_URL matches your server endpoint
```

**"Invalid response" errors:**
- Ensure the model ID matches what's loaded in vLLM
- Verify you're using a compatible vLLM version

## License

MIT — see [LICENSE](LICENSE)
