"""Drive headless Chrome over the DevTools protocol to screenshot the Streamlit app.

    python3 scripts/capture_screenshots.py <output-folder> [app-url]   # app must be running

Needs Google Chrome and the `websockets` package.

AI disclosure: written with help from Claude Code (Anthropic's AI coding assistant). See README, "Use of AI".
"""
import asyncio
import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = Path(sys.argv[1])
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8502"
PORT = 9333
OUT.mkdir(parents=True, exist_ok=True)


class Page:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def cmd(self, method, **params):
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def js(self, expr):
        r = await self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    async def settle(self, timeout=40, quiet=2.0):
        """Wait until Streamlit has charts and its 'running' widget has been gone for `quiet` seconds."""
        t0, calm = time.time(), None
        while time.time() - t0 < timeout:
            busy = await self.js(
                "(()=>{const s=document.querySelector('[data-testid=\"stStatusWidget\"]');"
                "const running = s && /running|connecting/i.test(s.innerText||'');"
                "const charts=document.querySelectorAll('[data-testid=\"stPlotlyChart\"]').length;"
                "return running || charts===0;})()")
            if busy:
                calm = None
            elif calm is None:
                calm = time.time()
            elif time.time() - calm > quiet:
                return
            await asyncio.sleep(0.4)
        print("   (settle timeout)")

    async def goto(self, url):
        await self.cmd("Page.navigate", url=url)
        await asyncio.sleep(2)
        await self.settle()

    async def tab(self, label):
        ok = await self.js(
            f"(()=>{{const b=[...document.querySelectorAll('[role=\"tab\"]')].find(x=>x.innerText.includes({json.dumps(label)}));"
            "if(!b) return false; b.click(); return true;})()")
        assert ok, f"tab {label} not found"
        await asyncio.sleep(1.5)
        await self.settle()
        await asyncio.sleep(1.0)

    async def guess(self, label="Going up"):
        await self.js(f"(()=>{{const l=[...document.querySelectorAll('label')].find(x=>x.innerText.includes({json.dumps(label)})); if(l) l.click(); return !!l;}})()")
        await asyncio.sleep(1.5)
        await self.settle()

    async def rect(self, js_element):
        return await self.js(
            f"(()=>{{const e=({js_element}); if(!e) return null; const r=e.getBoundingClientRect();"
            "return {x:r.left, y:r.top, width:r.width, height:r.height};})()")

    async def shot(self, name, clip=None, pad=12):
        params = {"format": "png", "captureBeyondViewport": False}
        if clip:
            params["clip"] = {"x": max(clip["x"] - pad, 0), "y": max(clip["y"] - pad, 0),
                              "width": clip["width"] + 2 * pad, "height": clip["height"] + 2 * pad, "scale": 1}
        data = (await self.cmd("Page.captureScreenshot", **params))["data"]
        (OUT / f"{name}.png").write_bytes(base64.b64decode(data))
        print("saved", name, clip and {k: round(v) for k, v in clip.items()})


VISIBLE_CHARTS = ("[...document.querySelectorAll('[data-testid=\"stPlotlyChart\"]')]"
                  ".filter(e=>e.offsetParent!==null && e.getBoundingClientRect().width>0)")
MAIN_BLOCK = "document.querySelector('[data-testid=\"stMainBlockContainer\"]') || document.querySelector('.block-container')"


def from_heading_to_chart(heading_text, chart_index=0):
    """Rect spanning from a visible heading/text down to the bottom of the n-th visible chart after it."""
    return (f"(()=>{{const h=[...document.querySelectorAll('h1,h2,h3,p,strong')].find(x=>x.offsetParent!==null && x.innerText.includes({json.dumps(heading_text)}));"
            f"const cs={VISIBLE_CHARTS}.filter(c=>!h || c.getBoundingClientRect().top>=h.getBoundingClientRect().top);"
            f"const c=cs[{chart_index}]; if(!h||!c) return null; const a=h.getBoundingClientRect(), b=c.getBoundingClientRect();"
            "const m=document.querySelector('[data-testid=\"stMainBlockContainer\"]').getBoundingClientRect();"
            "return {getBoundingClientRect:()=>({left:m.left, top:a.top-8, width:m.width, height:b.bottom-a.top+8})};})()")


async def main():
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                             f"--remote-debugging-port={PORT}", f"--user-data-dir={OUT}/profile",
                             "--no-first-run", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
                ws_url = next(p["webSocketDebuggerUrl"] for p in pages if p["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        async with websockets.connect(ws_url, max_size=200 * 2**20) as ws:
            p = Page(ws)
            await p.cmd("Page.enable")
            await p.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark"}])

            # 1. Full app view (viewport screenshot) - mission 1, Mongolia country average
            await p.cmd("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=2, mobile=False)
            await p.goto(f"{BASE}/?mission=1")
            await p.guess("Going up")
            await p.shot("01_app_mission1")

            # Tall viewport so whole sections fit without scrolling
            await p.cmd("Emulation.setDeviceMetricsOverride", width=1440, height=2600, deviceScaleFactor=2, mobile=False)
            await asyncio.sleep(1.5)
            await p.settle()
            await p.shot("02_investigate_mongolia", await p.rect(from_heading_to_chart("Air temperature · Mongolia")))

            # 3. Map tab
            await p.tab("Where is it changing")
            await p.shot("03_map", await p.rect(from_heading_to_chart("Mongolia average, per decade")))
            await p.shot("03b_map_only", await p.rect(VISIBLE_CHARTS + "[0]"), pad=0)

            # 4. Mongolia insights seasonal chart
            await p.tab("Mongolia insights")
            await p.shot("04_insights_seasons", await p.rect(from_heading_to_chart("Seasons tell different stories", 0)))
            await p.shot("04b_insights_metrics", await p.rect(from_heading_to_chart("Mongolia as a whole", 0)))

            # 5. Mission 3 compare (fresh visit so the link applies)
            await p.cmd("Emulation.setDeviceMetricsOverride", width=1440, height=3200, deviceScaleFactor=2, mobile=False)
            await p.goto(f"{BASE}/?mission=3")
            await p.guess("Going down")
            await p.shot("05_compare_arctic", await p.rect(from_heading_to_chart("Compare:", 0)))

            # 6. What is changing scan for South Gobi (mission 5)
            await p.goto(f"{BASE}/?mission=5")
            await p.tab("What is changing")
            await p.shot("06_scan_gobi", await p.rect(
                "(()=>{const h=[...document.querySelectorAll('p')].find(x=>x.offsetParent!==null && x.innerText.startsWith('Every variable at'));"
                "const t=[...document.querySelectorAll('[data-testid=\"stDataFrame\"]')].find(x=>x.offsetParent!==null);"
                "if(!h||!t) return null; const a=h.getBoundingClientRect(), b=t.getBoundingClientRect();"
                "const m=document.querySelector('[data-testid=\"stMainBlockContainer\"]').getBoundingClientRect();"
                "return {getBoundingClientRect:()=>({left:m.left, top:a.top-8, width:m.width, height:b.bottom-a.top+8})};})()"))
    finally:
        proc.terminate()


asyncio.run(main())
