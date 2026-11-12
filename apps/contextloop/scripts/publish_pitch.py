#!/usr/bin/env python3
"""`make publish-pitch`: upload the rendered pitch video to the ContextLoop media bucket and refresh CloudFront.

Publishes, under /pitch/ on the CloudFront distribution created by `make media-infra`:
  contextloop-pitch.mp4, .vtt (captions), -poster.jpg, and index.html (a public watch page to share with customers).
Then records the links in contextloop/ui/pitch/published.json (tracked in git), which the Architecture page reads, so the app
plays the hosted video. Refuses to upload while a render is running, or if the video doesn't decode cleanly.

Needs (on the host): the AWS CLI signed in, Terraform, ffmpeg.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "contextloop" / "ui" / "assets" / "video"
PITCH_DIR = ROOT / "contextloop" / "ui" / "pitch"
INFRA = ROOT / "infra" / "media"
FILES = [  # local name, content type, cache-control
    ("contextloop-pitch.mp4", "video/mp4", "public, max-age=86400"),
    ("contextloop-pitch.vtt", "text/vtt; charset=utf-8", "public, max-age=86400"),
    ("contextloop-pitch-poster.jpg", "image/jpeg", "public, max-age=86400"),
]


def sh(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def outputs() -> dict:
    try:
        out = json.loads(sh(["terraform", f"-chdir={INFRA}", "output", "-json"]))
    except subprocess.CalledProcessError:
        out = {}
    if not out.get("bucket"):
        sys.exit("The media stack doesn't exist yet: run `make media-infra` first.")
    return {k: v["value"] for k, v in out.items()}


def check_video(mp4: Path) -> float:
    if subprocess.run(["pgrep", "-f", "scripts/render_pitch_video.py"], capture_output=True).returncode == 0:
        sys.exit("A pitch render is running right now; publish when it has finished.")
    if not mp4.exists():
        sys.exit(f"No rendered video at {mp4.relative_to(ROOT)}: run `make pitch-video` first.")
    print("Checking the video decodes cleanly…")
    errors = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "null", "-"], capture_output=True, text=True).stderr
    if errors.strip():
        sys.exit(f"The video has decode errors, so it wasn't published. Re-render it.\n{errors[:400]}")
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]))


def main() -> None:
    out = outputs()
    mp4 = VIDEO_DIR / "contextloop-pitch.mp4"
    seconds = check_video(mp4)
    version = hashlib.sha256(mp4.read_bytes()).hexdigest()[:12]
    base, bucket = out["base_url"], out["bucket"]

    for name, ctype, cache in FILES:
        src = VIDEO_DIR / name
        if not src.exists():
            sys.exit(f"Missing {src.relative_to(ROOT)}")
        print(f"Uploading {name} ({src.stat().st_size / 1e6:.1f} MB)")
        sh(["aws", "s3", "cp", str(src), f"s3://{bucket}/pitch/{name}", "--content-type", ctype, "--cache-control", cache,
            "--only-show-errors"])

    page = (PITCH_DIR / "share.html").read_text()
    page = page.replace("{{BASE}}", base).replace("{{V}}", version).replace("{{MINUTES}}", str(max(1, round(seconds / 60))))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
    print("Uploading the watch page")
    sh(["aws", "s3", "cp", f.name, f"s3://{bucket}/pitch/index.html", "--content-type", "text/html; charset=utf-8",
        "--cache-control", "public, max-age=300", "--only-show-errors"])
    Path(f.name).unlink()

    print("Refreshing CloudFront")
    sh(["aws", "cloudfront", "create-invalidation", "--distribution-id", out["distribution_id"], "--paths", "/pitch/*", "/",
        "--query", "Invalidation.Id", "--output", "text"])

    published = {
        "page_url": f"{base}/",  # the distribution's root serves the watch page (pitch/index.html)
        "video_url": f"{base}/pitch/contextloop-pitch.mp4?v={version}",
        "captions_url": f"{base}/pitch/contextloop-pitch.vtt?v={version}",
        "poster_url": f"{base}/pitch/contextloop-pitch-poster.jpg?v={version}",
        "version": version,
        "seconds": round(seconds, 1),
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (PITCH_DIR / "published.json").write_text(json.dumps(published, indent=2) + "\n")
    print(f"\nPublished version {version} ({seconds / 60:.1f} min).\n"
          f"  Share with customers: {published['page_url']}\n"
          f"  The Architecture page now plays it from CloudFront (rebuild the app: docker compose up -d --build app).\n"
          f"  CloudFront refreshes within a few minutes.")


if __name__ == "__main__":
    main()
