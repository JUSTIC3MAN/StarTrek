#!/usr/bin/env python3
"""Comfort MCP server: lets a local AI (LM Studio, Goose, Open WebUI, Claude Desktop...) drive Comfort.
stdio JSON-RPC, standard library only. Talks to the Comfort watcher through inbox\\ and out\\ files and
starts "Start Comfort.bat" itself when Comfort isn't running."""
import base64, io, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
def P(*a): return os.path.join(ROOT, *a)

RULES = ("Comfort generates images with Krea 2 on Justice's PC. Rules: finish the whole set he asked for, then let him judge; "
         "for changes write a fresh prompt; never upscale unless he says he likes that exact image (then use upscale); "
         "battle arenas use a high three-quarter camera about 35 degrees down with a big open floor filling the lower two thirds. "
         "Prompts: one dense paragraph covering subject, composition and camera angle, environment, lighting, art style and medium, colors and mood.")

def log(m): print(m, file=sys.stderr, flush=True)

def status_text():
    try:
        with open(P("status.txt"), encoding="utf-8") as f: s = f.read().strip()
        return s, time.time() - os.path.getmtime(P("status.txt"))
    except OSError:
        return "never started", 1e9

def comfort_alive():
    s, age = status_text()
    if age < 30: return True
    return age < 900 and (" running " in s or "starting" in s or "image-to-prompt" in s)

def ensure_comfort():
    if comfort_alive(): return True
    if os.name == "nt":
        subprocess.Popen('cmd /c start "Comfort" /min "%s"' % P("Start Comfort.bat"), cwd=ROOT)
    for _ in range(40):
        time.sleep(1.5)
        if comfort_alive(): return True
    return False

def clean(t): return re.sub(r"\s+", " ", str(t)).strip()

def write_job(name, lines):
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", name or "job").strip("_")[:40] or "job"
    name, i = base, 2
    while os.path.exists(P("out", name)) or os.path.exists(P("inbox", name + ".txt")):
        name, i = "%s_%d" % (base, i), i + 1
    tmp = P("inbox", "." + name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f: f.write("\n".join(["#name " + name] + lines) + "\n")
    os.replace(tmp, P("inbox", name + ".txt"))
    return name

def result(name, wait, preview=True, prompts=False):
    t0 = time.time()
    while time.time() - t0 < wait:
        done = P("out", name, "_done.txt")
        if os.path.exists(done):
            time.sleep(0.3)
            with open(done, encoding="utf-8") as f: text = f.read()
            if prompts and os.path.exists(P("out", name, "_prompts.txt")):
                with open(P("out", name, "_prompts.txt"), encoding="utf-8") as f: text += "\nPROMPTS:\n" + f.read()
            out = [{"type": "text", "text": "job %s finished\n%s" % (name, text)}]
            sheet = P("out", name, "_sheet.jpg")
            if preview and os.path.exists(sheet):
                try:
                    from PIL import Image
                    im = Image.open(sheet).convert("RGB")
                    if im.width > 1024: im = im.resize((1024, int(im.height * 1024 / im.width)))
                    b = io.BytesIO(); im.save(b, "JPEG", quality=80); data = b.getvalue()
                except Exception:
                    with open(sheet, "rb") as f: data = f.read()
                out.append({"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/jpeg"})
            return out
        err = P("jobs", "failed", name + ".error.txt")
        if os.path.exists(err):
            with open(err, encoding="utf-8") as f: return [{"type": "text", "text": "job %s FAILED:\n%s" % (name, f.read()[-900:])}]
        time.sleep(1.5)
    return [{"type": "text", "text": "job %s still running (%s). Call check_job with name=%s in a minute." % (name, status_text()[0], name)}]

def opts(preset=None, size=None, n=None, seed=None, style=None):
    l = []
    if preset: l.append("#preset " + clean(preset))
    if size: l.append("#size " + clean(size))
    if n: l.append("#n %d" % int(n))
    if seed not in (None, ""): l.append("#seed %d" % int(seed))
    if style: l.append("#style " + clean(style))
    return l

# ------------------------------------------------------------------ tools
def t_generate(prompts, preset=None, size=None, n=1, seed=None, style=None, name=None, wait=240, preview=True, **_):
    if isinstance(prompts, str): prompts = [prompts]
    if not ensure_comfort(): return [{"type": "text", "text": "Comfort did not start - ask Justice to open 'Start Comfort.bat'."}]
    job = write_job(name or "gen", opts(preset, size, n, seed, style) + [clean(p) for p in prompts if clean(p)])
    return result(job, float(wait), preview)

def t_generate_from_image(image, direction="", size=None, preset=None, n=1, seed=None, name=None, wait=240, preview=True, **_):
    if not ensure_comfort(): return [{"type": "text", "text": "Comfort did not start."}]
    job = write_job(name or "from_image", opts(preset, size, n, seed) + ["#i2p " + clean(image), clean(direction) or "-"])
    return result(job, float(wait), preview, prompts=True)

def t_image_to_prompt(image, direction="", wait=180, **_):
    if not ensure_comfort(): return [{"type": "text", "text": "Comfort did not start."}]
    job = write_job("i2p", ["#wf i2p", "#i2p " + clean(image), clean(direction) or "-"])
    return result(job, float(wait), False, prompts=True)

def t_upscale(job, image_id, size, wait=300, **_):
    with open(P("out", job, "_manifest.json"), encoding="utf-8") as f: m = json.load(f)
    row = next((r for r in m["rows"] if r["id"] == image_id or (r.get("file") or "").startswith(image_id)), None)
    if not row: raise ValueError("no image %s in job %s" % (image_id, job))
    prompt = clean(m["full_prompts"][row["id"]])
    if not ensure_comfort(): return [{"type": "text", "text": "Comfort did not start."}]
    j = write_job("%s_%s_up" % (job, row["id"]), ["#style none", "#size " + row["size"], "#seed %d" % int(row["seed"]), "#final " + clean(size), prompt])
    return result(j, float(wait), True)

def t_check_job(name, wait=120, **_):
    return result(name, float(wait), True, prompts=True)

def t_list_presets(**_):
    with open(P("presets.json"), encoding="utf-8") as f: pr = json.load(f)
    with open(P("styles.json"), encoding="utf-8") as f: st = json.load(f)
    lines = []
    for k, v in pr.items():
        if k.startswith("_"): continue
        size = v.get("size") or "%s @ %s MP" % (v.get("aspect", "1:1"), v.get("mp", 1))
        lines.append("%s: %s%s%s" % (k, size, ("  style=" + v["style"]) if v.get("style") else "", ("  (" + v["note"] + ")") if v.get("note") else ""))
    return [{"type": "text", "text": "PRESETS\n" + "\n".join(lines) + "\nSTYLES (appended to prompts): " + ", ".join(st)}]

def t_status(**_):
    s, age = status_text()
    jobs = sorted((d for d in os.listdir(P("out")) if os.path.isdir(P("out", d))), key=lambda d: os.path.getmtime(P("out", d)))[-8:]
    return [{"type": "text", "text": "Comfort: %s (%s, updated %.0fs ago)\nrecent jobs: %s" % (s, "running" if comfort_alive() else "NOT running", age, ", ".join(jobs))}]

S = lambda d: {"type": "string", "description": d}
I = lambda d: {"type": "integer", "description": d}
TOOLS = [
 {"name": "generate", "description": "Generate images with Krea 2 on Justice's PC and get back file paths plus a contact-sheet preview. " + RULES,
  "inputSchema": {"type": "object", "required": ["prompts"], "properties": {
     "prompts": {"type": "array", "items": {"type": "string"}, "description": "One prompt per image idea, each a single dense paragraph."},
     "preset": S("Optional preset name from list_presets (sets size and style)."),
     "size": S("Optional exact size WxH, multiples of 16, 1-2 megapixels, e.g. 1536x864 widescreen, 1024x1024, 864x1536 vertical."),
     "n": I("Images per prompt (default 1)."), "seed": I("Optional fixed seed."),
     "style": S("Optional style suffix name, or 'none'."), "name": S("Short job name, e.g. forest_arena.")}}},
 {"name": "generate_from_image", "description": "Read a reference image with the local Qwen3-VL image-to-prompt (Krea 2 workflow) and generate new image(s) from that prompt.",
  "inputSchema": {"type": "object", "required": ["image"], "properties": {
     "image": S("Image path: absolute Windows path, a file name in Comfort\\inputs, or JOB\\file.png from Comfort\\out."),
     "direction": S("Optional change to apply, e.g. 'recompose as a wide landscape'."),
     "size": S("Output size WxH, e.g. 1536x864."), "preset": S("Optional preset."), "n": I("Images (default 1)."), "seed": I("Optional seed."), "name": S("Job name.")}}},
 {"name": "image_to_prompt", "description": "Only describe an image as a Krea 2 prompt (no image generated).",
  "inputSchema": {"type": "object", "required": ["image"], "properties": {"image": S("Image path."), "direction": S("Optional creative direction.")}}},
 {"name": "upscale", "description": "ONLY after Justice says he likes a specific image: re-render it from its seed and upscale to size.",
  "inputSchema": {"type": "object", "required": ["job", "image_id", "size"], "properties": {
     "job": S("Job folder name, e.g. forest_arena."), "image_id": S("Image id like 01-2."), "size": S("Target WxH, e.g. 3840x2160.")}}},
 {"name": "check_job", "description": "Get the result of a job that was still running.",
  "inputSchema": {"type": "object", "required": ["name"], "properties": {"name": S("Job name returned earlier.")}}},
 {"name": "list_presets", "description": "List size presets and style suffixes.", "inputSchema": {"type": "object", "properties": {}}},
 {"name": "status", "description": "Is Comfort running, and the most recent jobs.", "inputSchema": {"type": "object", "properties": {}}},
]
CALLS = {"generate": t_generate, "generate_from_image": t_generate_from_image, "image_to_prompt": t_image_to_prompt, "upscale": t_upscale,
         "check_job": t_check_job, "list_presets": t_list_presets, "status": t_status}

def handle(msg):
    m = msg.get("method")
    if m == "initialize":
        pv = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return {"protocolVersion": pv, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "comfort", "version": "1.0"}, "instructions": RULES}
    if m == "ping": return {}
    if m == "tools/list": return {"tools": TOOLS}
    if m == "tools/call":
        p = msg.get("params") or {}
        fn = CALLS.get(p.get("name"))
        if not fn: return {"content": [{"type": "text", "text": "unknown tool %s" % p.get("name")}], "isError": True}
        try:
            return {"content": fn(**(p.get("arguments") or {})), "isError": False}
        except Exception as e:
            return {"content": [{"type": "text", "text": "error: %s" % e}], "isError": True}
    raise LookupError(m)

def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8"); sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except Exception: pass
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: msg = json.loads(line)
        except Exception: continue
        if "id" not in msg: continue
        try: out = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
        except LookupError: out = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "method not found"}}
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
