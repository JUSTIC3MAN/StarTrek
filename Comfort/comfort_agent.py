"""Comfort's local master AI: an Ollama tool-calling loop that drives Comfort.

GPU hand-off: before any ComfyUI job the language model is unloaded (Ollama keep_alive=0), so Krea gets
the whole GPU; after the job ComfyUI frees its memory and the model reloads on the next step.
"""
import base64, io, json, os, re, shutil, subprocess, threading, time, urllib.error, urllib.request

import comfort as C
import comfort_flows as F

DEFAULTS = {"url": "http://127.0.0.1:11434", "model": "qwen3.6:27b", "keep_alive": "15m", "vram_handoff": True,
            "num_ctx": 16384, "show_results": True, "max_steps": 14, "think": True}

def cfg():
    d = dict(DEFAULTS)
    d.update(C.CFG.get("llm") or {})
    return d

def _post(path, data, timeout=900):
    req = urllib.request.Request(cfg()["url"].rstrip("/") + path, data=json.dumps(data).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError("Ollama %s: %s" % (e.code, e.read().decode("utf-8", "ignore")[:300]))

def status():
    c = cfg()
    try:
        with urllib.request.urlopen(c["url"].rstrip("/") + "/api/tags", timeout=3) as r:
            names = [m.get("name") for m in json.loads(r.read()).get("models", [])]
        has = any(n == c["model"] or n == c["model"] + ":latest" for n in names)
        return {"up": True, "model": c["model"], "installed": has, "models": names}
    except Exception:
        return {"up": False, "model": c["model"], "installed": False, "models": []}

_OLLAMA_LOCK = threading.Lock()

def find_ollama():
    c = cfg()
    for p in (c.get("ollama_exe"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
              shutil.which("ollama")):
        if p and os.path.isfile(p):
            return p
    return None

def ensure_ollama(timeout=60):
    """Start Ollama's server (hidden, no tray window) if it isn't running. True when it answers."""
    if status()["up"]:
        return True
    exe = find_ollama()
    if not exe:
        C.log("Ollama is not installed (run 'Install Ollama.bat')")
        return False
    with _OLLAMA_LOCK:
        if status()["up"]:
            return True
        C.log("starting Ollama: %s serve" % exe)
        subprocess.Popen([exe, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x08000000 if os.name == "nt" else 0)
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(1)
            if status()["up"]:
                C.log("Ollama is up after %.0fs" % (time.time() - t0))
                return True
    C.log("Ollama did not start")
    return False

def unload():
    try:
        _post("/api/generate", {"model": cfg()["model"], "keep_alive": 0}, timeout=60)
    except Exception as e:
        C.log("llm unload: %s" % e)

def b64_image(path, max_side=1024):
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((max_side, max_side))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=82)
        return base64.b64encode(b.getvalue()).decode()
    except Exception:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

def rel_url(path):
    path = os.path.abspath(path)
    for base, url in ((C.P("out"), "/out/"), (C.P("inputs"), "/inputs/")):
        if path.startswith(os.path.abspath(base) + os.sep):
            return url + os.path.relpath(path, base).replace(os.sep, "/")
    return None


# ------------------------------------------------------------------ tools
def _done(outdir):
    try:
        with open(os.path.join(outdir, "_done.txt"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = "no result file in %s" % outdir
    pr = os.path.join(outdir, "_prompts.txt")
    if os.path.exists(pr):
        with open(pr, encoding="utf-8") as f:
            text += "\nPROMPTS USED:\n" + f.read()[:3000]
    job = os.path.basename(outdir)
    text = "job folder: %s (refer to files as %s/<file>)\n%s" % (job, job, text)
    sheet = os.path.join(outdir, "_sheet.jpg")
    return text, (sheet if os.path.exists(sheet) else None)

REPLACED = {"Krea 2 RedCraft (ClaudeComfy)": "Krea 2 RedCraft (Comfort)",
            "DaSiWa MiniMax H3 (ClaudeComfy)": "MiniMax H3 Director (Comfort)"}
UI_ONLY = {"MiniMax H3 Seed Hunter (ClaudeComfy)"}   # needs ComfyUI's own window (UI-only wiring) - not runnable from Comfort

def agent_workflows():
    return [w for w in F.list_workflows() if w not in UI_ONLY]

def t_list_workflows(**_):
    w = agent_workflows()
    missing = [u for u in F.ui_workflows() if u not in w and u not in REPLACED and u not in UI_ONLY]
    return ("Workflows ready to run (name - what it is):\n" + ("\n".join("%s - %s" % (n, F.summary(n) or "no guide yet") for n in w) or "none") +
            ("\nSaved in ComfyUI but not converted yet (ask Justice to press Convert): " + ", ".join(missing) if missing else "") +
            "\nUse these instead of originals that cannot be converted: " + "; ".join("%s -> %s" % kv for kv in REPLACED.items()) +
            "\nOnly usable inside ComfyUI's own window (do not run): " + ", ".join(sorted(UI_ONLY))), None

def t_describe_workflow(workflow, filter=None, **_):
    name, lines = F.describe(workflow, filter)
    g = F.guide(name)
    head = ("GUIDE FOR %s:\n%s\n\n" % (name, g)) if g and not filter else ""
    return (head + "SETTINGS of %s - every editable setting as 'node_id | title | input=value'. "
            "Change any of them with run_workflow set={'node_id.input': value}.\n" % name) + "\n".join(lines[:300]), None

def t_prompt_guide(topic="krea2", **_):
    t = str(topic).lower()
    fn = "_h3_prompting" if ("h3" in t or "video" in t or "minimax" in t) else "_krea2_prompting"
    with open(C.P("guides", fn + ".md"), encoding="utf-8") as f:
        return f.read(), None

def t_find_images(query="", limit=8, **_):
    """Search gallery job names, file names and the prompts behind each image."""
    import difflib
    q = C._norm(query)
    hits = []
    for j, t, files in C.gallery_jobs():
        prompts = ""
        for fn in ("_prompts.txt", "_texts.txt", "_manifest.json"):
            p = os.path.join(C.P("out"), j, fn)
            if os.path.exists(p):
                with open(p, encoding="utf-8", errors="ignore") as f:
                    prompts += f.read()[:4000].lower()
        for f in files:
            name = C._norm(j + f)
            s = difflib.SequenceMatcher(None, q, C._norm(j)).ratio()
            if q and (q in name):
                s = max(s, 0.9)
            words = [w for w in re.findall(r"[a-z]{3,}", str(query).lower())]
            if words:
                s = max(s, 0.5 * sum(1 for w in words if w in prompts) / len(words) + 0.3 * sum(1 for w in words if w in (j + f).lower()) / len(words))
            hits.append((s, j + "/" + f))
    hits.sort(key=lambda x: -x[0])
    out = [h for s, h in hits[:int(limit)] if s > 0.2] or [h for _, h in hits[:int(limit)]]
    return "Best matches (use these exact paths):\n" + "\n".join(out), None

def t_star_trek(action, song="", mode="", text="", shot="", value="", **_):
    """Star Trek production (Justice 2026-10-27): runs Star Trek\\Overseer\\overseer.py <action> ..."""
    import subprocess, sys
    ov = os.path.normpath(C.P("..", "Overseer", "overseer.py"))
    args = [str(action)] + ([str(song)] if song else [])
    if action == "mode":
        args.append(str(mode or "auto"))
    if action in ("redo", "trim", "transition") or (action == "shots" and shot):
        args.append(str(shot))
    if action in ("trim", "transition") and value:
        args += str(value).split()
    if action == "setshots":
        tmp = os.path.normpath(C.P("..", "Overseer", "logs", "agent_shots.txt"))
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(str(text))
        args.append(tmp)
    exe = sys.executable[:-5] + ".exe" if sys.executable.lower().endswith("pythonw.exe") else sys.executable
    r = subprocess.run([exe, ov] + args, capture_output=True, text=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return (((r.stdout or "") + (r.stderr or "")).strip() or "done")[:3000], None

def t_look_at(image, **_):
    path = C.find_file(str(image))
    rel = os.path.relpath(path, C.P("out")).replace(os.sep, "/") if path.startswith(C.P("out")) else os.path.basename(path)
    return "Showing you %s (the image is attached next)." % rel, path

def _auto_size(path, short=768, mult=32):
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
    except Exception:
        return 1376, 768
    if w >= h:
        return int(round(w * short / h / mult)) * mult, short
    return short, int(round(h * short / w / mult)) * mult

def normalize_h3(prompt, mode, duration):
    """Repair an H3 prompt so it always has the official structure, whatever the model wrote."""
    p = re.sub(r"^\s*(T2VA|I2VA|FL2VA|L2VA|REF2VA)\s*[:.]?\s*\n+", "", str(prompt).strip(), flags=re.I)
    if "integrated_multimodal_description:" not in p:
        body, rest = p, ""
        m = re.search(r"\n\s*overall_soundscape:", p)
        if m:
            body, rest = p[:m.start()], p[m.start():]
        p = "integrated_multimodal_description: " + body.strip() + rest
    if not re.search(r"integrated_multimodal_description:\s*\[Shot 1\]", p):
        p = p.replace("integrated_multimodal_description:", "integrated_multimodal_description: [Shot 1]", 1)
        p = p.replace("[Shot 1]  ", "[Shot 1] ")
    if "non_diegetic_music:" not in p:
        p += "\nnon_diegetic_music: N/A"
    shots = [int(x) for x in re.findall(r"\[Shot (\d+)\]", p)] or [1]
    d = "%.2f" % float(duration)
    if mode != "T2VA" and "<Picture 1>" not in p:
        if mode == "I2VA":
            line = "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
        elif mode == "FL2VA":
            line = ("How the reference pictures align with the target video \u2014 <Picture 1> (from [Shot 1]) aligns with the 0.00-second mark "
                    "of the target video; <Picture 2> (from [Shot %d]) aligns with the %s-second mark of the target video." % (max(shots), d))
        else:
            line = "<Picture 1> (from [Shot %d]) aligns with the %s-second mark of the target video." % (max(shots), d)
        p = line + "\n\n" + p
    return p

def t_make_video(prompt, mode="T2VA", duration=5, width=None, height=None, start_image=None, end_image=None,
                 n=1, seed="random", name=None, **_):
    mode = str(mode).upper()
    if mode not in ("T2VA", "I2VA", "FL2VA", "L2VA"):
        raise ValueError("mode must be T2VA, I2VA, FL2VA or L2VA")
    if mode == "I2VA" and not start_image:
        raise ValueError("I2VA needs start_image")
    if mode == "L2VA" and not end_image:
        raise ValueError("L2VA needs end_image")
    prompt = normalize_h3(prompt, mode, duration)
    wf = "MiniMax H3 Director (Comfort)"
    _, g = F.load_workflow(wf)
    used = []
    nid = F.director_id(g)
    ref = start_image if mode in ("I2VA", "FL2VA") and start_image else end_image
    if not width or not height:
        width, height = _auto_size(C.find_file(str(ref))) if (ref and mode != "T2VA") else (1376, 768)
    w, h = max(32, int(round(int(width) / 32)) * 32), max(32, int(round(int(height) / 32)) * 32)   # H3 needs multiples of 32
    pics = ([start_image] if mode in ("I2VA", "FL2VA") and start_image else []) + \
           ([end_image] if mode in ("L2VA", "FL2VA") and end_image else [])
    C.ensure_comfy()
    items = []
    for i, path in enumerate(pics):
        src = C.find_file(str(path))
        used.append(os.path.relpath(src, C.P("out")).replace(os.sep, "/") if src.startswith(C.P("out")) else os.path.basename(src))
        up = C.upload_image(src)
        try:
            from PIL import Image
            with Image.open(src) as im:
                sw, sh = im.size
        except Exception:
            sw = sh = 0
        items.append({"id": "image-comfort-%d" % i, "enabled": True, "order": i, "slot": i, "start": 0, "duration": 1,
                      "type": "image", "value": up, "thumbnail": None, "source_width": sw, "source_height": sh})
    sets = {nid + ".mode": mode, nid + ".prompt": prompt, nid + ".width": w, nid + ".height": h,
            nid + ".duration": float(duration),
            nid + ".timeline_data": json.dumps({"version": 1, "items": items, "prompt_blocks": []}),
            nid + ".builder_state": json.dumps({"prompt_mode": "simple", "simple_prompt": prompt})}
    outdir, _ = F.run_flow({"workflow": wf, "set": sets, "raw_set": {nid + ".external_prompt_overwrite": prompt},
                            "n": n, "seed": seed, "name": name or "video", "free_after": False})
    text, sheet = _done(outdir)
    return ("%s video %dx%d, %ss, images used: %s\nPROMPT SENT (structure checked):\n%s\n" % (mode, w, h, duration, ", ".join(used) or "none", prompt)) + text, sheet

def t_run_workflow(workflow, set=None, images=None, n=1, seed="random", name=None, **_):
    if workflow in UI_ONLY:
        raise ValueError("%s only works inside ComfyUI's own window. For video use make_video." % workflow)
    outdir, _ = F.run_flow({"workflow": workflow, "set": set or {}, "images": images or {}, "n": n, "seed": seed,
                            "name": name, "free_after": False})
    return _done(outdir)

def _krea_job(name, extra, prompts_or_lines):
    job = {"name": name}
    job.update({k: v for k, v in extra.items() if v not in (None, "")})
    job["prompts"] = prompts_or_lines
    outdir, _ = C.run_job(C.parse_json(job), name or "gen")
    return _done(outdir)

def t_generate(prompts, size=None, preset=None, n=1, seed=None, style=None, name=None, **_):
    if isinstance(prompts, str):
        prompts = [prompts]
    return _krea_job(name or "gen", {"size": size, "preset": preset, "n": n, "seed": seed, "style": style}, prompts)

def t_generate_from_image(image, direction="", size=None, preset=None, n=1, seed=None, name=None, **_):
    return _krea_job(name or "from_image", {"size": size, "preset": preset, "n": n, "seed": seed, "i2p": image},
                     [direction or "-"])

def t_image_to_prompt(image, direction="", **_):
    text, _ = _krea_job("i2p", {"wf": "i2p", "i2p": image}, [direction or "-"])
    return text, None

def t_upscale(image, size, **_):
    outdir, fn = F.upscale_image(image, size)
    return _done(outdir)

def t_list_presets(**_):
    lines = []
    for k, v in C.PRESETS.items():
        if k.startswith("_"):
            continue
        w, h = C.parse_wh(v.get("size")) or C.gen_dims(v.get("aspect", "1:1"), v.get("mp", 1.0))
        lines.append("%s: %dx%d%s" % (k, w, h, ("  " + v["note"]) if v.get("note") else ""))
    return "\n".join(lines), None

def t_recent_results(limit=8, **_):
    d = C.P("out")
    jobs = sorted((j for j in os.listdir(d) if os.path.isdir(os.path.join(d, j))), key=lambda j: os.path.getmtime(os.path.join(d, j)))[-int(limit):]
    out = []
    for j in reversed(jobs):
        files = [f for f in os.listdir(os.path.join(d, j)) if f.lower().endswith((".png", ".jpg", ".webp", ".mp4", ".webm", ".gif")) and not f.startswith("_")]
        out.append("%s: %s" % (j, ", ".join(files[:12])))
    return "\n".join(out) or "no results yet", None

S = lambda d: {"type": "string", "description": d}
I = lambda d: {"type": "integer", "description": d}
def tool(name, desc, props, req=()):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": list(req)}}}

TOOLS = [
    tool("generate", "Quick image generation with the Krea 2 RedCraft workflow. One dense paragraph per prompt.",
         {"prompts": {"type": "array", "items": {"type": "string"}, "description": "Prompts, one per image idea."},
          "size": S("WxH, multiples of 16, 1-2 megapixels, e.g. 1536x864 widescreen."), "preset": S("Optional preset name."),
          "n": I("Images per prompt."), "seed": I("Optional fixed seed."), "style": S("Optional style suffix name or 'none'."),
          "name": S("Short job name.")}, ["prompts"]),
    tool("generate_from_image", "Turn a reference image into a prompt (local image-to-prompt) and render new image(s) from it with Krea 2.",
         {"image": S("Image path: inputs file name, job/file from results, or absolute path."), "direction": S("Optional change to apply."),
          "size": S("Output WxH."), "preset": S("Optional preset."), "n": I("Images."), "name": S("Job name.")}, ["image"]),
    tool("image_to_prompt", "Only write a Krea 2 prompt that describes an image.", {"image": S("Image path."), "direction": S("Optional direction.")}, ["image"]),
    tool("make_video", "Make a video WITH AUDIO using MiniMax H3 (Justice's DaSiWa H3 Director workflow). The prompt MUST follow the H3 "
         "structure - call prompt_guide topic='h3' first if unsure. Takes minutes.",
         {"prompt": S("Full H3 prompt: (alignment line for I2VA/FL2VA/L2VA, blank line) integrated_multimodal_description: [Shot 1] ... / overall_soundscape: ... / non_diegetic_music: ..."),
          "mode": S("T2VA (text only), I2VA (start from start_image), FL2VA (start_image to end_image), L2VA (end on end_image)."),
          "duration": {"type": "number", "description": "Seconds, 2-15 (default 5)."},
          "width": I("Width, multiple of 32. Leave out to match the start/end image (short side 768)."), "height": I("Height, multiple of 32. Leave out to match the image."),
          "start_image": S("First-frame image: gallery reference like 'pond_wide_v3' or 'rez_forest/01-2...png', or an attached file name."), "end_image": S("Last-frame image (FL2VA/L2VA), same kinds of reference."),
          "n": I("Takes (different seeds)."), "name": S("Job name.")}, ["prompt"]),
    tool("find_images", "Find gallery images by name or by what they show (searches job names, file names and the prompts that made them).",
         {"query": S("e.g. 'pond wide 3', 'moaning tree stump', 'forest arena'"), "limit": I("How many results.")}, ["query"]),
    tool("look_at", "Look at a gallery image or attached image yourself (it is shown to you).", {"image": S("Gallery reference or file name.")}, ["image"]),
    tool("star_trek", "Justice's music-video production (Star Trek: SongMap -> shot list -> Comfort -> Overseer checks -> FilmCraft edit in Preview). Use whenever he talks about his song videos, also when Claude is out of tokens.",
         {"action": S("review (start here: short summary) | redo (re-render a shot) | trim (cut the end of a shot, slowed to fit; value = percent) | transition (set the transition INTO a shot; value = e.g. 'film_dissolve 16' or 'cross_zoom 12 strength=40') | rebuild | pause | resume | mode | shots (with shot = a label or section word, to see only those lines) | setshots | songmap | rules | readme"), "shot": S("Shot label (a01 or a01_harbour_wide) or, for shots, a section word."), "value": S("For trim: percent (10-20). For transition: name and params."), "song": S("Song project name, e.g. conqueress."),
          "mode": S("For mode: auto (keep producing), check (only check), off."), "text": S("For setshots: the complete new shot list.")}, ["action"]),
    tool("prompt_guide", "Full prompting rules: topic 'krea2' (images) or 'h3' (MiniMax H3 video+audio).", {"topic": S("krea2 or h3")}, ["topic"]),
    tool("list_workflows", "List every ComfyUI workflow Comfort can run, with what each is for.", {}),
    tool("describe_workflow", "Show every editable setting of a workflow as 'node_id | title | input=value'. Use before run_workflow.",
         {"workflow": S("Workflow name from list_workflows."), "filter": S("Optional text filter, e.g. 'seed' or 'prompt'.")}, ["workflow"]),
    tool("run_workflow", "Run any workflow with any settings changed. set keys are 'node_id.input' (or 'Node Title.input').",
         {"workflow": S("Workflow name."), "set": {"type": "object", "description": "Settings to change, e.g. {\"46.value\": \"a forest\", \"13.width\": 1536}."},
          "images": {"type": "object", "description": "Image inputs to fill, e.g. {\"44.image\": \"pond.jpg\"}."},
          "n": I("How many runs (new random seed each)."), "seed": S("'random' (default), 'keep' or a number."), "name": S("Job name.")}, ["workflow"]),
    tool("upscale", "ONLY when Justice says he likes a specific image: upscale that image file to an exact size.",
         {"image": S("job/file of the image."), "size": S("Target WxH, e.g. 3840x2160.")}, ["image", "size"]),
    tool("list_presets", "List size presets.", {}),
    tool("recent_results", "List recent result folders and their files.", {"limit": I("How many jobs.")}),
]
FUNCS = {"generate": t_generate, "generate_from_image": t_generate_from_image, "image_to_prompt": t_image_to_prompt,
         "list_workflows": t_list_workflows, "describe_workflow": t_describe_workflow, "run_workflow": t_run_workflow,
         "upscale": t_upscale, "list_presets": t_list_presets, "recent_results": t_recent_results,
         "make_video": t_make_video, "prompt_guide": t_prompt_guide, "find_images": t_find_images, "look_at": t_look_at, "star_trek": t_star_trek}
HEAVY = {"generate", "generate_from_image", "image_to_prompt", "run_workflow", "upscale", "make_video"}


def benchmark():
    """Free the GPU, then time a vision + tool-call request twice (cold load, then warm). Writes llm_benchmark.json."""
    from PIL import Image, ImageDraw
    if not ensure_ollama():
        raise RuntimeError("Ollama is not running and could not be started")
    C.comfy_free()
    unload()
    time.sleep(2)
    im = Image.new("RGB", (256, 256), (220, 30, 30))
    ImageDraw.Draw(im).ellipse((80, 80, 176, 176), fill=(30, 200, 60))
    b = io.BytesIO(); im.save(b, "PNG")
    c = cfg()
    req = {"model": c["model"], "stream": False, "think": False, "keep_alive": c["keep_alive"], "options": {"num_ctx": int(c["num_ctx"])},
           "messages": [{"role": "user", "content": "Look at the image. Call report_colors with the background color and the circle color.",
                         "images": [base64.b64encode(b.getvalue()).decode()]}],
           "tools": [tool("report_colors", "Report the colors in the image", {"background": S("color"), "circle": S("color")}, ["background", "circle"])]}
    runs = []
    for label in ("cold", "warm"):
        d = _post("/api/chat", req)
        ns = 1e9
        calls = (d.get("message") or {}).get("tool_calls") or []
        args = (calls[0].get("function") or {}).get("arguments") if calls else {}
        runs.append({"run": label, "load_s": round(d.get("load_duration", 0) / ns, 1),
                     "prompt_tokens_per_s": round(d.get("prompt_eval_count", 0) / max(1e-9, d.get("prompt_eval_duration", 1) / ns), 1),
                     "gen_tokens_per_s": round(d.get("eval_count", 0) / max(1e-9, d.get("eval_duration", 1) / ns), 1),
                     "total_s": round(d.get("total_duration", 0) / ns, 1), "tool_call": args})
    out = {"model": c["model"], "time": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": runs}
    with open(C.P("llm_benchmark.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    C.log("llm benchmark: %s" % json.dumps(runs))
    return out


# ------------------------------------------------------------------ agent
class Agent:
    def __init__(self):
        self.reset()

    def reset(self):
        self.messages, self.display, self.busy, self.stop, self.status = [], [], False, False, "ready"

    def show(self, kind, text, images=None):
        self.display.append({"i": len(self.display), "kind": kind, "text": text, "images": images or [], "t": time.time()})

    def system_prompt(self):
        try:
            with open(C.P("AGENT_PROMPT.txt"), encoding="utf-8") as f:
                base = f.read().strip()
        except OSError:
            base = "You are Justice's image director for Comfort."
        try:
            with open(C.P("guides", "_agent_rules.md"), encoding="utf-8") as f:
                rules = f.read().strip()
        except OSError:
            rules = ""
        wfs = "\n".join("- %s: %s" % (n, F.summary(n) or "") for n in agent_workflows())
        gal = []
        for j, t, files in C.gallery_jobs()[:15]:
            gal.append("- %s: %s%s" % (j, ", ".join(files[:6]), " (+%d more)" % (len(files) - 6) if len(files) > 6 else ""))
        return (base + "\n\n" + rules + "\n\nWORKFLOWS AVAILABLE:\n" + wfs +
                "\n\nGALLERY (newest first; refer to images as job/file, or just the job name for its first image):\n" + "\n".join(gal))

    def send(self, text, attachments=None):
        if self.busy:
            raise RuntimeError("busy")
        self.busy, self.stop = True, False
        threading.Thread(target=self._run, args=(text, attachments or []), daemon=True).start()

    def _chat(self, msgs):
        c = cfg()
        body = {"model": c["model"], "messages": msgs, "tools": TOOLS, "stream": False, "keep_alive": c["keep_alive"],
                "options": {"num_ctx": int(c["num_ctx"])}}
        if c.get("think") is not None:
            body["think"] = bool(c["think"])
        try:
            return _post("/api/chat", body)
        except RuntimeError as e:
            if "think" in str(e).lower():
                body.pop("think", None)
                return _post("/api/chat", body)
            raise

    def _payload(self):
        # keep only the two most recent images in context
        seen, out = 0, []
        for m in reversed(self.messages):
            m2 = dict(m)
            if m2.get("images"):
                seen += 1
                if seen > 2:
                    m2.pop("images")
            out.append(m2)
        return [{"role": "system", "content": self.system_prompt()}] + list(reversed(out))

    def _run(self, text, attachments):
        c = cfg()
        try:
            C.reload_data()
            msg = {"role": "user", "content": text}
            urls = []
            if attachments:
                paths = [C.find_file(a) for a in attachments]
                msg["content"] += "\n[attached images: %s]" % ", ".join(os.path.basename(p) for p in paths)
                msg["images"] = [b64_image(p) for p in paths]
                urls = [u for u in (rel_url(p) for p in paths) if u]
            self.messages.append(msg)
            self.show("user", text, urls)
            if not status()["up"]:
                self.status = "starting Ollama"
                if not ensure_ollama():
                    raise RuntimeError("Ollama is not installed or would not start - run 'Install Ollama.bat' in the Comfort folder")
            if c["vram_handoff"] and C.comfy_up():
                self.status = "freeing GPU memory in ComfyUI"
                C.comfy_free()          # the AI must load fully on the GPU, not spill to CPU
            for step in range(int(c["max_steps"])):
                if self.stop:
                    self.show("status", "stopped")
                    break
                self.status = "thinking (loading %s)" % c["model"] if step == 0 else "thinking"
                resp = self._chat(self._payload())
                m = resp.get("message") or {}
                entry = {"role": "assistant", "content": m.get("content") or ""}
                if m.get("tool_calls"):
                    entry["tool_calls"] = m["tool_calls"]
                self.messages.append(entry)
                if entry["content"].strip():
                    self.show("assistant", entry["content"].strip())
                calls = m.get("tool_calls") or []
                if not calls:
                    break
                for call in calls:
                    fn = (call.get("function") or {}).get("name")
                    args = (call.get("function") or {}).get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args or "{}")
                        except ValueError:
                            args = {}
                    self.show("tool", "%s %s" % (fn, json.dumps(args, ensure_ascii=False)[:400]))
                    heavy = fn in HEAVY
                    if heavy and c["vram_handoff"]:
                        self.status = "unloading %s - GPU goes to ComfyUI" % c["model"]
                        unload()
                    self.status = "running %s" % fn if heavy else "working"
                    try:
                        if fn not in FUNCS:
                            raise ValueError("unknown tool %s" % fn)
                        out, sheet = FUNCS[fn](**args)
                    except Exception as e:
                        out, sheet = "error: %s" % e, None
                    if heavy and c["vram_handoff"]:
                        C.comfy_free()
                    self.messages.append({"role": "tool", "content": out[:6000], "tool_name": fn})
                    self.show("result", out[:2000], [rel_url(sheet)] if sheet else [])
                    if sheet and (c["show_results"] or fn == "look_at"):
                        label = "[Comfort] the image you asked to look at" if fn == "look_at" else "[Comfort] contact sheet of that result"
                        self.messages.append({"role": "user", "content": label, "images": [b64_image(sheet)]})
            else:
                self.show("status", "stopped after %d steps" % c["max_steps"])
        except Exception as e:
            self.show("error", str(e))
        finally:
            self.busy, self.status = False, "ready"
