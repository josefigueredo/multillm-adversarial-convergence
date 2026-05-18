# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "websockets>=12",
#   "httpx>=0.27",
# ]
# ///
"""Smoke test the deployed AWS stack end-to-end.

Spawns N WebSocket viewer clients against the real AWS API Gateway, fires
a sequence of control patches as the presenter would, and asserts every
viewer receives every broadcast.

Config is read from `pro/.deploy.env` (SLIDES_API_KEY required).

Run:
    uv run pro/scripts/smoke_test_aws.py
    uv run pro/scripts/smoke_test_aws.py --viewers 5 --patches 4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time

import httpx
import websockets

# Endpoints baked at deploy time. If you redeploy with a different
# project_name, regenerate this file or pass --ws/--control on the CLI.
DEFAULTS = {
    "ws_url": "wss://ori5i6vq1m.execute-api.us-east-1.amazonaws.com/prod",
    "control_url": "https://3xat0cxfhd.execute-api.us-east-1.amazonaws.com/control",
    "state_url": "https://3xat0cxfhd.execute-api.us-east-1.amazonaws.com/state",
}

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def _load_api_key(env_path: pathlib.Path) -> str:
    if not env_path.exists():
        sys.exit(f"{RED}FAIL{RESET} expected {env_path} with SLIDES_API_KEY=...")
    for line in env_path.read_text().splitlines():
        if line.startswith("SLIDES_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"{RED}FAIL{RESET} SLIDES_API_KEY missing from {env_path}")


async def _viewer(viewer_id: int, ws_url: str, ready: asyncio.Event, inbox: list[dict], stop: asyncio.Event) -> None:
    """One subscriber. The $connect-time initial state is best-effort on AWS
    API Gateway (see backend/handlers/connect.py), so we don't block on it —
    we just record whatever arrives during the test window."""
    async with websockets.connect(ws_url, open_timeout=10) as ws:
        # Best-effort: drain any initial-state message that may show up
        # within ~1.5s of connect. If none arrives, fine — we use the
        # HTTP /state endpoint as the authoritative starting point.
        try:
            initial = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.5))
            inbox.append(initial)
            print(f"  {DIM}viewer #{viewer_id} connected (got initial state v{initial['version']}){RESET}")
        except asyncio.TimeoutError:
            print(f"  {DIM}viewer #{viewer_id} connected (no initial push — that's fine){RESET}")
        ready.set()
        while not stop.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                break
            inbox.append(json.loads(raw))


async def run(viewers: int, patches: int, ws_url: str, control_url: str, state_url: str, api_key: str) -> int:
    failures: list[str] = []

    print(f"{DIM}WS:      {ws_url}{RESET}")
    print(f"{DIM}Control: {control_url}{RESET}")
    print(f"{DIM}Viewers: {viewers}    Patches: {patches}{RESET}\n")

    # Start viewers and wait for each to receive its initial snapshot.
    inboxes: list[list[dict]] = [[] for _ in range(viewers)]
    ready_events = [asyncio.Event() for _ in range(viewers)]
    stop = asyncio.Event()
    tasks = [
        asyncio.create_task(_viewer(i, ws_url, ready_events[i], inboxes[i], stop))
        for i in range(viewers)
    ]
    await asyncio.gather(*(e.wait() for e in ready_events))
    print(f"{GREEN}OK{RESET} all {viewers} viewers connected\n")

    # Authoritative starting version from the HTTP /state endpoint.
    async with httpx.AsyncClient(timeout=5) as http:
        start_state = (await http.get(state_url)).json()
    start_version = start_state["version"]
    print(f"{DIM}starting state: slide={start_state['slide']}, version={start_version}{RESET}")

    # Fire control patches from this process (acting as the presenter).
    print(f"{DIM}sending {patches} control patches…{RESET}")
    target_slides = [(start_version + i + 1) % 40 + 1 for i in range(patches)]
    async with httpx.AsyncClient(timeout=10) as http:
        for slide in target_slides:
            t0 = time.monotonic()
            r = await http.post(
                control_url,
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json={"slide": slide},
            )
            dt = (time.monotonic() - t0) * 1000
            if r.status_code != 200:
                failures.append(f"control POST slide={slide} returned {r.status_code}: {r.text[:200]}")
                continue
            print(f"  {DIM}POST slide={slide:<3} {r.status_code} {dt:.0f}ms{RESET}")
            await asyncio.sleep(0.4)  # let the broadcast propagate before next patch

    # Give the last broadcast a moment to land, then stop viewers.
    await asyncio.sleep(1.0)
    stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)

    # Verify each viewer saw every patch broadcast in order. Filter for
    # only the messages whose version is > start_version — that excludes
    # any best-effort initial-state push.
    for i, box in enumerate(inboxes):
        broadcasts = [m for m in box if m.get("version", -1) > start_version]
        seen_slides = [m["slide"] for m in broadcasts]
        if seen_slides != target_slides:
            failures.append(
                f"viewer #{i} broadcast mismatch\n"
                f"  expected slides: {target_slides}\n"
                f"  actually saw:    {seen_slides}\n"
                f"  full inbox versions: {[m.get('version') for m in box]}"
            )
        versions = [m["version"] for m in broadcasts]
        if versions != sorted(versions) or len(set(versions)) != len(versions):
            failures.append(f"viewer #{i} version sequence not monotonic: {versions}")

    # Final state should reflect the last patch sent.
    async with httpx.AsyncClient(timeout=5) as http:
        final = (await http.get(state_url)).json()
    if final["slide"] != target_slides[-1]:
        failures.append(f"state endpoint reports slide={final['slide']}, expected {target_slides[-1]}")

    print()
    if failures:
        print(f"{RED}FAIL — {len(failures)} assertion(s){RESET}")
        for f in failures:
            print(f"  • {f}")
        return 1

    print(f"{GREEN}PASS{RESET} every viewer received every broadcast in order, state endpoint matches")
    print(f"{DIM}final state: slide={final['slide']}, version={final['version']}{RESET}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Smoke test the deployed AWS slides backend.")
    p.add_argument("--viewers", type=int, default=3, help="number of WS subscribers (default 3)")
    p.add_argument("--patches", type=int, default=3, help="number of control patches to send (default 3)")
    p.add_argument("--ws", default=DEFAULTS["ws_url"])
    p.add_argument("--control", default=DEFAULTS["control_url"])
    p.add_argument("--state", default=DEFAULTS["state_url"])
    p.add_argument("--env", default=pathlib.Path(__file__).resolve().parent.parent / ".deploy.env")
    args = p.parse_args()

    api_key = _load_api_key(pathlib.Path(args.env))
    return asyncio.run(run(args.viewers, args.patches, args.ws, args.control, args.state, api_key))


if __name__ == "__main__":
    sys.exit(main())
