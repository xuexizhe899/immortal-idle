#!/usr/bin/env python3
"""Batch image generation driven by a prompt preset.

Design rules (tasks/T10-art-pipeline.md):
  * generate, then download immediately - image URLs are never persisted
  * local de-dup by hash(style + subject + size + model)
  * every successful call recorded in assets/manifest.json
  * hard call cap via ASSET_MAX_CALLS

Usage:
  python tools/gen_assets.py --probe
  python tools/gen_assets.py --preset trial
  python tools/gen_assets.py --preset trial --dry-run
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
STYLE_PATH = ROOT / "config" / "style" / "style.json"
MANIFEST_PATH = ROOT / "assets" / "manifest.json"
RAW_DIR = ROOT / "assets" / "raw"


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"version": 1, "calls": 0, "items": []}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def digest(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
    return h.hexdigest()[:16]


def build_prompt(style: dict, item: dict) -> str:
    if item.get("kind") == "scene":
        base = style["scene_prompt"]
        avoid = style.get("scene_avoid") or style.get("negative_prompt", "")
        prompt = f"{base}. Subject: {item['subject']}"
        if avoid:
            prompt = f"{prompt}. Avoid: {avoid}"
        return prompt
    return f"{style['style_prompt']}. Subject: {item['subject']}"


def request_image(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    size: str,
) -> dict:
    body = {"model": model, "prompt": prompt, "n": 1, "size": size}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = client.post(f"{base_url}/v1/images/generations", json=body, headers=headers)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    payload = resp.json()
    items = payload.get("data") or []
    if not items:
        raise RuntimeError(f"no data: {json.dumps(payload, ensure_ascii=False)[:300]}")

    first = items[0]
    usage = payload.get("usage")
    if first.get("b64_json"):
        return {"kind": "b64", "value": first["b64_json"], "usage": usage}
    if first.get("url"):
        return {"kind": "url", "value": first["url"], "usage": usage}
    raise RuntimeError(f"unsupported payload keys: {list(first)}")


def save_payload(client: httpx.Client, payload: dict, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if payload["kind"] == "b64":
        dest.write_bytes(base64.b64decode(payload["value"]))
    else:
        resp = client.get(payload["value"], timeout=180)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="trial")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()

    env = read_env(ENV_PATH)
    api_key = env.get("CENTOS_API_KEY", "")
    base_url = env.get("CENTOS_BASE_URL", "").rstrip("/")
    model = env.get("CENTOS_MODEL", "")
    max_calls = int(env.get("ASSET_MAX_CALLS", "300"))

    if not api_key or not base_url or not model:
        print("[gen] .env missing CENTOS_API_KEY / CENTOS_BASE_URL / CENTOS_MODEL", file=sys.stderr)
        return 2

    style = json.loads(STYLE_PATH.read_text(encoding="utf-8"))
    fallback_size = style.get("fallback_size", "1024x1024")

    if args.probe:
        with httpx.Client(timeout=180) as client:
            print(f"[probe] model={model} base={base_url}")
            started = time.time()
            payload = request_image(
                client, base_url, api_key, model,
                "a red apple on a wooden table, soft daylight", fallback_size,
            )
            size_bytes = save_payload(client, payload, RAW_DIR / "_probe.png")
            print(f"[probe] ok kind={payload['kind']} bytes={size_bytes} "
                  f"elapsed={int((time.time() - started) * 1000)}ms usage={payload['usage']}")
        return 0

    preset = json.loads(
        (ROOT / "assets" / "prompts" / f"{args.preset}.json").read_text(encoding="utf-8")
    )

    manifest = load_manifest()
    if manifest["calls"] >= max_calls:
        print(f"[gen] call cap reached: {manifest['calls']}/{max_calls}", file=sys.stderr)
        return 3

    done = {item["key"]: item for item in manifest["items"]}
    size_override: str | None = None

    with httpx.Client(timeout=300) as client:
        for item in preset["items"]:
            key = item["key"]
            prompt = build_prompt(style, item)
            size = size_override or (
                style.get("scene_size", fallback_size)
                if item.get("kind") == "scene"
                else style.get("size", fallback_size)
            )
            call_hash = digest(model, size, prompt)

            existing = done.get(key)
            if existing and not args.force and existing.get("hash") == call_hash:
                if (ROOT / existing["file"]).exists():
                    print(f"[gen] skip {key} (same prompt, file present)")
                    continue

            if args.dry_run:
                print(f"[gen] dry-run {key}: size={size} chars={len(prompt)}")
                continue

            print(f"[gen] {key}: size={size} ...", flush=True)
            started = time.time()
            try:
                try:
                    payload = request_image(client, base_url, api_key, model, prompt, size)
                except RuntimeError as exc:
                    if size != fallback_size and "HTTP 4" in str(exc):
                        print(f"[gen] {key}: size {size} rejected, retry {fallback_size}")
                        payload = request_image(
                            client, base_url, api_key, model, prompt, fallback_size
                        )
                        size_override = fallback_size
                        size = fallback_size
                        call_hash = digest(model, size, prompt)
                    else:
                        raise
            except Exception as exc:
                print(f"[gen] {key} failed: {exc}", file=sys.stderr)
                continue

            manifest["calls"] = int(manifest.get("calls", 0)) + 1
            dest = RAW_DIR / item["file"]
            size_bytes = save_payload(client, payload, dest)
            elapsed = int((time.time() - started) * 1000)

            record = {
                "key": key,
                "kind": item.get("kind", "portrait"),
                "file": dest.relative_to(ROOT).as_posix(),
                "hash": call_hash,
                "model": model,
                "size": size,
                "prompt": prompt,
                "bytes": size_bytes,
                "elapsed_ms": elapsed,
                "usage": payload.get("usage"),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            manifest["items"] = [i for i in manifest["items"] if i.get("key") != key]
            manifest["items"].append(record)
            manifest["updated_at"] = record["created_at"]
            save_manifest(manifest)
            print(f"[gen] {key} -> {record['file']} ({size_bytes // 1024} KB, {elapsed} ms)")

    print(f"[gen] done, total calls={manifest['calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
