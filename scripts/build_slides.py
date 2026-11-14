"""Render demo/slides.html to a PDF (and PNG previews) with headless Google Chrome.

    python3 scripts/build_slides.py                          # GitHub link only
    python3 scripts/build_slides.py --app-url https://...    # also show the live app link

Needs Google Chrome and the `websockets` package (pip install websockets).

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import html
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
PDF = DEMO / "Earth_System_Trend_Detective_slides.pdf"
PORT = 9334
W, H = 1920, 1080


async def render(source: Path, n_slides: int) -> None:
    profile = tempfile.mkdtemp(prefix="slides-chrome-")
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={profile}", "--no-first-run", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
                ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        async with websockets.connect(ws_url, max_size=500 * 2**20) as ws:
            counter = 0

            async def cmd(method, **params):
                nonlocal counter
                counter += 1
                my = counter
                await ws.send(json.dumps({"id": my, "method": method, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == my:
                        if "error" in msg:
                            raise RuntimeError(f"{method}: {msg['error']}")
                        return msg.get("result", {})

            await cmd("Page.enable")
            await cmd("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
            await cmd("Page.navigate", url=source.as_uri())
            await asyncio.sleep(2.5)
            pdf = await cmd("Page.printToPDF", printBackground=True, preferCSSPageSize=True,
                            paperWidth=W / 96, paperHeight=H / 96, marginTop=0, marginBottom=0, marginLeft=0, marginRight=0)
            PDF.write_bytes(base64.b64decode(pdf["data"]))
            print(f"wrote {PDF.relative_to(ROOT)} ({PDF.stat().st_size / 1e6:.1f} MB)")
            (DEMO / "preview").mkdir(exist_ok=True)
            for i in range(n_slides):
                shot = await cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                                 clip={"x": 0, "y": i * H, "width": W, "height": H, "scale": 0.5})
                out = DEMO / "preview" / f"slide-{i + 1}.png"
                out.write_bytes(base64.b64decode(shot["data"]))
            print(f"wrote {n_slides} previews to demo/preview/")
    finally:
        proc.terminate()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-url", default="")
    args = ap.parse_args()
    src = (DEMO / "slides.html").read_text()
    if args.app_url:
        url = html.escape(args.app_url)
        shown = html.escape(args.app_url.removeprefix("https://").removeprefix("http://").rstrip("/"))
        link = f'<p style="font-size:27px;"><span class="muted">Live app:</span><br><a href="{url}">{shown}</a></p>'
        src = src.replace("<!--APP_LINK-->", link)
    n_slides = src.count('<section class="slide"')
    tmp = DEMO / "_render.html"  # same folder so relative image paths work
    tmp.write_text(src)
    try:
        asyncio.run(render(tmp, n_slides))
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
