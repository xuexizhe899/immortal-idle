#!/usr/bin/env python3
"""Batch image generation driven by a prompt preset.

Design rules (tasks/T10-art-pipeline.md):
  * download immediately; signed response URLs stay only in an ignored recovery cache
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
import re
import shutil
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


class GenerationError(RuntimeError):
    """Public error text must never include an API key or signed image URL."""

    def __init__(self, message: str, *, unsupported_size: bool = False):
        super().__init__(message)
        self.unsupported_size = unsupported_size


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
    temporary = MANIFEST_PATH.with_suffix(".json.part")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(MANIFEST_PATH)


def project_path(value: str | Path) -> Path:
    """Keep preset-controlled output paths inside the repository."""
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("asset path must stay inside the repository")
    return path


def digest(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
    return h.hexdigest()[:16]


def build_prompt(style: dict, item: dict) -> str:
    if item.get("prompt"):
        return item["prompt"]
    kind = item.get("kind", "portrait")
    if kind == "scene":
        base = style["scene_prompt"]
        avoid = style.get("scene_avoid") or style.get("negative_prompt", "")
        prompt = f"{base}. Subject: {item['subject']}"
        if avoid:
            prompt = f"{prompt}. Avoid: {avoid}"
        return prompt
    if kind == "terrain":
        avoid = style.get("scene_avoid") or style.get("negative_prompt", "")
        prompt = style["terrain_prompt"]
        if item.get("subject"):
            prompt = f"{prompt}. Additional: {item['subject']}"
        if avoid:
            prompt = f"{prompt}. Avoid: {avoid}"
        return prompt
    if kind == "sprite":
        # 洋红底供本地 chroma-key 抠图，负面词不再拼（避免与 magenta 背景冲突）
        return f"{style['sprite_prompt']}. Subject: {item['subject']}"
    if kind == "building":
        base = style["building_prompt"]
        avoid = style.get("scene_avoid") or style.get("negative_prompt", "")
        prompt = f"{base}. Subject: {item['subject']}"
        if avoid:
            prompt = f"{prompt}. Avoid: {avoid}"
        return prompt
    if kind == "city":
        # 主城全景 prompt 已在 style 里写死布局，不再拼 Subject
        avoid = style.get("scene_avoid") or style.get("negative_prompt", "")
        prompt = style["city_prompt"]
        if item.get("subject"):
            prompt = f"{prompt}. Additional: {item['subject']}"
        if avoid:
            prompt = f"{prompt}. Avoid: {avoid}"
        return prompt
    avoid = style.get("negative_prompt", "")
    base = style["style_prompt"]
    if item.get("background") == "magenta":
        base = base.replace("plain light warm-gray background", "pure flat solid magenta background (#FF00FF) for chroma-key extraction")
    prompt = f"{base}. Subject: {item['subject']}"
    if avoid:
        prompt = f"{prompt}. Avoid: {avoid}"
    return prompt


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
    endpoint = base_url if base_url.endswith("/v1") else f"{base_url}/v1"
    resp = client.post(f"{endpoint}/images/generations", json=body, headers=headers)
    if resp.status_code >= 400:
        # Inspect privately for the only safe automatic generation retry.
        # Provider responses may contain credentials or signed URLs: never print them.
        detail = resp.text.lower()
        unsupported = resp.status_code in (400, 422) and bool(
            re.search(r"(?:unsupported|invalid|not supported|must be).{0,80}(?:size|resolution)|(?:size|resolution).{0,80}(?:unsupported|invalid|not supported|must be)", detail)
        )
        raise GenerationError(f"HTTP {resp.status_code}: image request rejected", unsupported_size=unsupported)

    payload = resp.json()
    items = payload.get("data") or []
    if not items:
        raise GenerationError("provider returned no image data")

    first = items[0]
    usage = payload.get("usage")
    if first.get("b64_json"):
        return {"kind": "b64", "value": first["b64_json"], "usage": usage}
    if first.get("url"):
        return {"kind": "url", "value": first["url"], "usage": usage}
    raise GenerationError("provider returned an unsupported image payload")


def save_payload(client: httpx.Client, payload: dict, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if payload["kind"] == "b64":
        content = base64.b64decode(payload["value"], validate=True)
    else:
        resp = client.get(payload["value"], timeout=180, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content
    temporary = dest.with_suffix(dest.suffix + ".part")
    temporary.write_bytes(content)
    temporary.replace(dest)
    return dest.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="trial", help="preset name or repository-relative JSON path")
    parser.add_argument("--output-subdir", help="subdirectory beneath assets/raw")
    parser.add_argument("--master-dir", help="copy successful originals to this repository-relative directory")
    parser.add_argument("--max-attempts", type=int, default=4, help="maximum generation requests in this invocation, including failures")
    parser.add_argument("--retry-failed", action="store_true", help="explicitly retry a previously failed/uncertain request")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()

    env = read_env(ENV_PATH)
    api_key = env.get("CENTOS_API_KEY", "")
    base_url = env.get("CENTOS_BASE_URL", "").rstrip("/")
    model = env.get("CENTOS_MODEL", "")
    max_calls = int(env.get("ASSET_MAX_CALLS", "300"))

    if not args.dry_run and (not api_key or not base_url or not model):
        print("[gen] .env missing CENTOS_API_KEY / CENTOS_BASE_URL / CENTOS_MODEL", file=sys.stderr)
        return 2
    if args.max_attempts < 1:
        parser.error("--max-attempts must be positive")

    style = json.loads(STYLE_PATH.read_text(encoding="utf-8"))
    fallback_size = style.get("fallback_size", "1024x1024")

    if args.probe:
        preset = {"items": [{"key": "_probe", "file": "_probe.png", "prompt": "a red apple on a wooden table, soft daylight", "size": fallback_size}]}
    else:
        preset_path = project_path(args.preset) if args.preset.endswith(".json") else ROOT / "assets" / "prompts" / f"{args.preset}.json"
        preset = json.loads(preset_path.read_text(encoding="utf-8"))
    output_dir = project_path(RAW_DIR / (args.output_subdir or preset.get("output_subdir", "")))
    if not output_dir.is_relative_to(RAW_DIR.resolve()):
        parser.error("--output-subdir must stay beneath assets/raw")
    master_value = args.master_dir or preset.get("master_dir")
    master_dir = project_path(master_value) if master_value else None

    manifest = load_manifest()
    done = {item["key"]: item for item in manifest["items"]}
    attempts = manifest.setdefault("attempts", [])
    local_attempts = 0
    failures = 0
    stop_after_error = False

    with httpx.Client(timeout=httpx.Timeout(600, connect=20)) as client:
        for item in preset["items"]:
            key = item["key"]
            prompt = build_prompt(style, item)
            kind = item.get("kind", "portrait")
            if kind in ("scene", "city", "terrain"):
                default_size = style.get("scene_size", fallback_size)
            elif kind in ("building", "sprite"):
                default_size = style.get("building_size", style.get("scene_size", fallback_size))
            else:
                default_size = style.get("size", fallback_size)
            size = item.get("size") or default_size
            call_hash = digest(style.get("version", ""), model, size, prompt)
            requested_hash = call_hash
            dest = project_path(output_dir / item["file"])
            if not dest.is_relative_to(output_dir):
                raise ValueError("preset file must stay inside the selected output directory")
            pending_path = dest.with_suffix(dest.suffix + ".pending.json")

            existing = done.get(key)
            if existing and not args.force and existing.get("requested_hash", existing.get("hash")) == requested_hash:
                completed_file = project_path(existing["file"])
                completed_master = project_path(existing["master"]) if existing.get("master") else None
                if args.dry_run and (completed_file.exists() or (completed_master and completed_master.exists())):
                    print(f"[gen] dry-run skip {key} (completed asset or master present)")
                    continue
                # Raw files are deliberately ignored. A clean checkout still has curated
                # masters: restore from them instead of paying to generate the same image.
                if not completed_file.exists() and completed_master and completed_master.exists():
                    completed_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(completed_master, completed_file)
                if completed_file.exists():
                    if completed_file != dest:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(completed_file, dest)
                    if master_dir:
                        master_dir.mkdir(parents=True, exist_ok=True)
                        selected_master = master_dir / dest.name
                        if completed_file != selected_master:
                            shutil.copy2(completed_file, selected_master)
                    print(f"[gen] skip {key} (same prompt, file present)")
                    continue

            if args.dry_run:
                print(f"[gen] dry-run {key}: size={size} chars={len(prompt)}")
                continue

            started = time.time()
            payload = None
            record = None
            if pending_path.exists() and not args.force:
                cached = json.loads(pending_path.read_text(encoding="utf-8"))
                if cached["record"].get("requested_hash", cached["record"]["hash"]) != requested_hash:
                    print(f"[gen] {key}: pending download belongs to another prompt; use its original preset", file=sys.stderr)
                    failures += 1
                    continue
                payload, record = cached["payload"], cached["record"]
                print(f"[gen] {key}: resuming saved image download (no generation call)", flush=True)
            else:
                previous = next((attempt for attempt in reversed(attempts) if attempt.get("key") == key and attempt.get("hash") == call_hash), None)
                if previous and previous["status"] in ("requesting", "uncertain", "failed", "generated") and not (args.retry_failed or args.force):
                    print(f"[gen] {key}: previous request {previous['status']}; not resending without --retry-failed", file=sys.stderr)
                    failures += 1
                    continue

                while payload is None:
                    if local_attempts >= args.max_attempts or manifest["calls"] >= max_calls:
                        print(f"[gen] {key}: generation attempt budget exhausted", file=sys.stderr)
                        failures += 1
                        break
                    local_attempts += 1
                    manifest["calls"] = int(manifest.get("calls", 0)) + 1
                    attempt = {"key": key, "hash": call_hash, "model": model, "size": size, "status": "requesting", "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                    attempts.append(attempt)
                    save_manifest(manifest)  # Count attempted billing before sending, even if interrupted.
                    print(f"[gen] {key}: size={size}, attempt={local_attempts}/{args.max_attempts} ...", flush=True)
                    try:
                        payload = request_image(client, base_url, api_key, model, prompt, size)
                    except GenerationError as exc:
                        attempt["status"] = "failed"
                        attempt["error"] = str(exc)
                        save_manifest(manifest)
                        if exc.unsupported_size and size != fallback_size:
                            size = fallback_size
                            call_hash = digest(style.get("version", ""), model, size, prompt)
                            print(f"[gen] {key}: explicit unsupported-size response; trying {fallback_size}", flush=True)
                            continue
                        print(f"[gen] {key}: {exc}; no automatic regeneration", file=sys.stderr)
                        failures += 1
                        stop_after_error = True
                        break
                    except Exception as exc:
                        attempt["status"] = "uncertain"
                        attempt["error"] = type(exc).__name__
                        save_manifest(manifest)
                        print(f"[gen] {key}: {type(exc).__name__}; request outcome uncertain, no automatic regeneration", file=sys.stderr)
                        failures += 1
                        stop_after_error = True
                        break
                if payload is None:
                    if stop_after_error:
                        break
                    continue
                record = {"key": key, "kind": item.get("kind", "portrait"), "file": dest.relative_to(ROOT).as_posix(), "hash": call_hash, "requested_hash": requested_hash, "model": model, "size": size, "style_version": style.get("version"), "prompt": prompt, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                # Private ignored cache permits download recovery without billing for a new image.
                pending_path.parent.mkdir(parents=True, exist_ok=True)
                pending_path.write_text(json.dumps({"record": record, "payload": payload}), encoding="utf-8")
                attempt["status"] = "generated"
                save_manifest(manifest)

            try:
                size_bytes = save_payload(client, payload, dest)
            except Exception as exc:
                print(f"[gen] {key}: download {type(exc).__name__}; rerun this preset to resume without regeneration", file=sys.stderr)
                failures += 1
                continue
            elapsed = int((time.time() - started) * 1000)
            record.update(bytes=size_bytes, elapsed_ms=elapsed, usage=payload.get("usage"))
            if master_dir:
                master_dir.mkdir(parents=True, exist_ok=True)
                master = master_dir / dest.name
                shutil.copy2(dest, master)
                record["master"] = master.relative_to(ROOT).as_posix()
            manifest["items"] = [i for i in manifest["items"] if i.get("key") != key]
            manifest["items"].append(record)
            manifest["updated_at"] = record["created_at"]
            save_manifest(manifest)
            pending_path.unlink(missing_ok=True)
            print(f"[gen] {key} -> {record['file']} ({size_bytes // 1024} KB, {elapsed} ms)")

    print(f"[gen] done, total calls={manifest['calls']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
