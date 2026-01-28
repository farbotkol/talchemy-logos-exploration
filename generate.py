#!/usr/bin/env python3
import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.openai.com/v1/images/generations"

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "logo"


def request_image(
    api_key: str,
    prompt: str,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "hd",
    style: str = "vivid",
) -> bytes:
    # Note: dall-e-3 does not support transparent backgrounds via API.
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
        "quality": quality,
        "style": style,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=body,
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Images API failed ({e.code}): {err}") from e

    data = payload.get("data", [{}])[0]
    b64 = data.get("b64_json")
    url = data.get("url")
    if b64:
        return base64.b64decode(b64)
    if url:
        # fallback if API returns URLs
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                return r.read()
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to download image: {e}") from e
    raise RuntimeError(f"Unexpected response: {json.dumps(payload)[:500]}")


def write_gallery(out_dir: Path, items: list[dict]) -> None:
    thumbs = "\n".join(
        [
            f"""
<figure>
  <a href=\"{it['file']}\"><img src=\"{it['file']}\" loading=\"lazy\" /></a>
  <figcaption><strong>{it['id']:02d}.</strong> {it['title']}<br/><small>{it['prompt']}</small></figcaption>
</figure>
""".strip()
            for it in items
        ]
    )
    html = f"""<!doctype html>
<meta charset=\"utf-8\" />
<title>T Alchemy — Logo Exploration</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 24px; font: 14px/1.4 ui-sans-serif, system-ui; background: #0b0f14; color: #e8edf2; }}
  h1 {{ font-size: 20px; margin: 0 0 8px; }}
  p {{ margin: 0 0 18px; color: #b7c2cc; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }}
  figure {{ margin: 0; padding: 12px; border: 1px solid #1e2a36; border-radius: 14px; background: #0f1620; }}
  img {{ width: 100%; height: auto; border-radius: 10px; display: block; background: #ffffff; }}
  figcaption {{ margin-top: 10px; color: #b7c2cc; }}
  small {{ color: #8ea2b2; }}
</style>
<h1>T Alchemy — 50 Logo Concepts (PNG)</h1>
<p>Generated concepts for review. Files are in <code>{out_dir.as_posix()}</code>.</p>
<div class=\"grid\">
{thumbs}
</div>
"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def main():
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Missing OPENAI_API_KEY", file=sys.stderr)
        return 2

    prompts_path = Path("prompts.json")
    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))

    ts = dt.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    out_dir = Path("out") / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    items_out = []
    for i, p in enumerate(prompts, start=1):
        print(f"[{i}/{len(prompts)}] {p['title']}")
        img_bytes = request_image(api_key, p["prompt"])
        fname = f"{p['id']:02d}-{slugify(p['title'])[:60]}.png"
        (out_dir / fname).write_bytes(img_bytes)
        items_out.append({
            "id": p["id"],
            "title": p["title"],
            "prompt": p["prompt"],
            "file": fname,
        })

    (out_dir / "generated.json").write_text(json.dumps(items_out, indent=2), encoding="utf-8")
    write_gallery(out_dir, items_out)
    print("\nWrote:", (out_dir / "index.html").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
