"""Shared tooling for the narrated demo videos: TTS, screencast recording and the final ffmpeg mix.

Adapted from CineSense (scripts/video/recorder.py). Run the video scripts with a Python that has edge-tts,
playwright, mutagen, imageio-ffmpeg and pygments installed (see scripts/video/README.md). Not part of the app and
not imported by it.
"""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from mutagen.mp3 import MP3

VOICE = "en-GB-RyanNeural"  # British English, like the app's English texts
RATE = "+5%"  # a touch faster than edge-tts' default
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1920, 1080  # video size in pixels
# The browser renders a 1536 × 864 CSS-pixel page at 1.25× (= 1920 × 1080 device pixels): the app's text stays
# readable in the video. Pointer coordinates below are CSS pixels.
VIEW_W, VIEW_H, SCALE = 1536, 864, 1.25
# without this flag the DevTools screencast delivers CSS-pixel frames (1536 × 864) even with device_scale_factor
BROWSER_ARGS = [f"--force-device-scale-factor={SCALE}"]

# A visible mouse pointer: screencasts don't show the real one. Follows mouse events and pulses on click.
CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('__demo_cursor')) return;
    const c = document.createElement('div');
    c.id = '__demo_cursor';
    c.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;' +
      'background:rgba(255,255,255,.85);border:2px solid rgba(0,0,0,.55);box-shadow:0 0 12px rgba(255,210,120,.8);' +
      'pointer-events:none;z-index:2147483647;transition:transform .07s linear;transform:translate(-100px,-100px)';
    document.documentElement.appendChild(c);
    let x = -100, y = -100, s = 1;
    const put = () => { c.style.transform = `translate(${x}px,${y}px) scale(${s})`; };
    addEventListener('mousemove', e => { x = e.clientX; y = e.clientY; put(); }, true);
    addEventListener('mousedown', () => { s = 0.6; put(); }, true);
    addEventListener('mouseup', () => { s = 1; put(); }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""


@dataclass
class Segment:
    key: str
    text: str
    audio: Path | None = None
    duration: float = 0.0
    start: float = 0.0  # seconds from the first video frame


async def synthesize(segments: list[Segment], out: Path, voice: str = VOICE, rate: str = RATE) -> None:
    """One mp3 per segment; cached by voice, rate and text so re-runs only re-synthesize what changed."""
    out.mkdir(parents=True, exist_ok=True)
    for s in segments:
        mp3 = out / f"{s.key}.mp3"
        txt = out / f"{s.key}.txt"
        key = f"{voice} {rate}\n{s.text}"
        if not (mp3.exists() and txt.exists() and txt.read_text() == key):
            for attempt in range(8):  # the service answers now and then with no audio: try again
                try:
                    await edge_tts.Communicate(s.text, voice, rate=rate).save(str(mp3))
                    break
                except edge_tts.exceptions.NoAudioReceived:
                    if attempt == 7:
                        raise
                    await asyncio.sleep(3 + 3 * attempt)
            txt.write_text(key)
        s.audio, s.duration = mp3, MP3(str(mp3)).info.length


@dataclass
class Screencast:
    """Records a page through the Chrome DevTools screencast (sharp JPEG frames with timestamps)."""

    page: object
    frames_dir: Path
    frames: list[tuple[float, Path]] = field(default_factory=list)
    t0: float | None = None
    cuts: list[tuple[float, float]] = field(default_factory=list)  # (from, to) seconds dropped from the video

    async def start(self) -> None:
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        for old in self.frames_dir.glob("*.jpg"):
            old.unlink()
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", lambda e: asyncio.ensure_future(self._frame(e)))
        await self.cdp.send(
            "Page.startScreencast", {"format": "jpeg", "quality": 90, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1}
        )
        while self.t0 is None:
            await asyncio.sleep(0.05)

    async def _frame(self, e: dict) -> None:
        ts = e["metadata"].get("timestamp") or time.time()
        if self.t0 is None:
            self.t0 = ts
        path = self.frames_dir / f"{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(e["data"]))
        self.frames.append((ts, path))
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": e["sessionId"]})
        except Exception:  # noqa: BLE001, S110 - the session may already be closed after stopScreencast
            pass

    def now(self) -> float:
        return time.time() - (self.t0 or time.time())

    async def wait_cut(self, awaitable, keep: float = 0.8) -> None:
        """Wait for something slow (an agent turn) and cut the dead time out of the video, keeping 'keep' s."""
        start = self.now()
        await awaitable
        end = self.now() - keep
        if end > start:
            self.cuts.append((start, end))

    def shift(self, t: float) -> float:
        """Recording time → video time after the cuts."""
        return t - sum(min(b, t) - a for a, b in self.cuts if a < t)

    async def stop(self, tail: float = 0.0) -> None:
        end = time.time() + tail
        while time.time() < end:
            await asyncio.sleep(0.1)
        self.end = self.now()
        await self.cdp.send("Page.stopScreencast")


async def narrate(rec: Screencast, seg: Segment, actions=None, pad: float = 0.7) -> None:
    """Start the segment's voice at 'now', run the actions alongside, and hold until both are done."""
    seg.start = rec.now()
    print(f"{seg.start:7.1f}s  {seg.key}", flush=True)
    if actions is not None:
        await actions()
    rest = seg.start + seg.duration + pad - rec.now()
    if rest > 0:
        await asyncio.sleep(rest)


def render(rec: Screencast, segments: list[Segment], out: Path, fps: int = 30) -> None:
    """Frames (variable rate) + voice clips at their offsets → H.264/AAC mp4."""
    work = rec.frames_dir.parent
    lst = work / "frames.txt"
    kept = [(t - rec.t0, p) for t, p in rec.frames if not any(a <= t - rec.t0 < b for a, b in rec.cuts)]
    times = [rec.shift(t) for t, _ in kept] + [rec.shift(rec.end)]
    end = times[-1]
    lines = []
    for i, (_, p) in enumerate(kept):
        lines += [f"file '{p}'", f"duration {max(times[i + 1] - times[i], 0.001):.4f}"]
    lines.append(f"file '{kept[-1][1]}'")
    lst.write_text("\n".join(lines) + "\n")

    voiced = [s for s in segments if s.audio is not None and s.duration > 0]
    timeline = [(str(s.audio), rec.shift(s.start)) for s in voiced]
    (work / "timeline.json").write_text(json.dumps({"end": end, "voice": timeline}, indent=1))
    mix_voice(timeline, end, work / "voice.wav")

    # Separate passes: mixing the voice in the same ffmpeg run as the long-frame video input dropped stretches of
    # audio (digital silence) whenever the video side stalled.
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst)]
    cmd += ["-i", str(work / "voice.wav"), "-map", "0:v", "-map", "1:a"]
    cmd += [
        "-vf",
        (
            f"fps={fps},scale={W}:{H}:flags=lanczos,format=yuv420p,fade=t=in:d=0.8,"
            f"fade=t=out:st={max(end - 1.0, 0):.2f}:d=1.0"
        ),
    ]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-t", f"{end:.2f}"]
    cmd += ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)


def mix_voice(timeline: list[tuple[str, float]], end: float, out: Path) -> None:
    """Voice clips at their offsets (seconds) → one loudness-normalised 48 kHz wav of length 'end'."""
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for path, _ in timeline:
        cmd += ["-i", path]
    delays = "".join(f"[{i}:a]adelay={int(t * 1000)}:all=1[a{i}];" for i, (_, t) in enumerate(timeline))
    mix = "".join(f"[a{i}]" for i in range(len(timeline)))
    fc = f"{delays}{mix}amix=inputs={len(timeline)}:normalize=0,loudnorm=I=-16:TP=-1.5,apad,atrim=0:{end:.2f}[a]"
    cmd += ["-filter_complex", fc, "-map", "[a]", "-ar", "48000", str(out)]
    subprocess.run(cmd, check=True)


# --- pointer helpers ---------------------------------------------------------------------------------------------

_pos = {"x": VIEW_W / 2, "y": VIEW_H / 2}


async def glide(page, x: float, y: float, ms: int = 700) -> None:
    """Move the pointer along a smooth curve in (wall-clock) ms, however slow each mouse event is."""
    x0, y0 = _pos["x"], _pos["y"]
    t0, dur = time.monotonic(), ms / 1000
    while True:
        t = min((time.monotonic() - t0) / dur, 1.0)
        e = t * t * (3 - 2 * t)  # smoothstep
        await page.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e)
        if t >= 1.0:
            break
        await asyncio.sleep(0.02)
    _pos.update(x=x, y=y)


SCROLL_Y_JS = """e => {
  const r = e.getBoundingClientRect();
  if (r.top < 70 || r.top > innerHeight * 0.75) window.scrollBy({ top: r.top - innerHeight * 0.3, behavior: 'smooth' });
}"""


async def glide_to(
    page, locator, ms: int = 700, dx: float = 0.5, dy: float = 0.5, only_y: bool = False
) -> tuple[float, float]:
    """Scroll the element into view, then glide the pointer to it. only_y=True scrolls the page vertically only
    (for elements wider than the viewport, which scroll_into_view would also scroll sideways)."""
    locator = locator.filter(visible=True).first
    for attempt in range(5):  # drifting rows and re-renders detach elements now and then
        try:
            if only_y:
                await locator.evaluate(SCROLL_Y_JS)
                await asyncio.sleep(0.7)
            else:
                await locator.scroll_into_view_if_needed(timeout=10000)
            box = await locator.bounding_box()
            if box:
                break
        except Exception:
            if attempt == 4:
                raise
        await asyncio.sleep(0.3)
    x, y = box["x"] + box["width"] * dx, box["y"] + box["height"] * dy
    x, y = min(max(x, 12), VIEW_W - 12), min(max(y, 12), VIEW_H - 12)
    await glide(page, x, y, ms)
    return x, y


async def click(page, locator, ms: int = 700, js: bool = False) -> None:
    """Glide to the element, then click; js=True for elements that keep moving (drifting rows)."""
    await glide_to(page, locator, ms)
    await asyncio.sleep(0.15)
    if js:
        await locator.filter(visible=True).first.evaluate("e => e.click()")
    else:
        await page.mouse.down()
        await page.mouse.up()
