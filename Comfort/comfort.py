#!/usr/bin/env python3
"""Comfort - batch prompt runner for ClaudeComfy (Krea 2 RedCraft + Krea 2 Identity Edit).

Drop a job file (.txt or .json) into inbox\\ . Comfort starts ComfyUI if needed, queues every
prompt, saves the images to out\\<job>\\, makes a contact sheet (_sheet.jpg) and a short
summary (_done.txt). See README.txt for the job format.

  comfort.py watch        keep watching inbox\\ (what "Start Comfort.bat" runs)
  comfort.py run FILE     run one job file and exit
  comfort.py presets      list presets with their generation sizes
"""
import json, os, sys, time, math, random, re, shutil, subprocess, uuid, traceback, threading
import urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
def P(*a): return os.path.join(ROOT, *a)

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

CFG = load_json(os.environ.get("COMFORT_CONFIG", P("config.json")))
PRESETS = load_json(P("presets.json"))
STYLES = load_json(P("styles.json"))
URL = CFG["comfy_url"].rstrip("/")
CLIENT_ID = "comfort-" + uuid.uuid4().hex[:8]
JOB_LOCK = threading.RLock()   # one ComfyUI job at a time (watcher, app, agent)

# ---------------------------------------------------------------- logging / status
def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with open(P("comfort.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def set_status(s):
    """A reader (e.g. Claude's device shell) can hold status.txt for an instant; on Windows the replace then fails
    with Access denied. Retry, and never let a status line kill a job (2026-10-27: it killed conqueress_keys_v1)."""
    tmp = P("status.txt.tmp")
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n"
    for _ in range(30):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(line)
            os.replace(tmp, P("status.txt"))
            return
        except OSError:
            time.sleep(0.1)

# ---------------------------------------------------------------- ComfyUI HTTP
def http(method, path, data=None, timeout=30, raw=False):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(URL + path, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b or b"null")

def comfy_up():
    try:
        http("GET", "/system_stats", timeout=3)
        return True
    except Exception:
        return False

def ensure_comfy():
    if comfy_up():
        return
    if not CFG.get("auto_start_comfy", True):
        raise RuntimeError("ComfyUI is not running at " + URL)
    log("ComfyUI not running - starting it")
    set_status("starting ComfyUI")
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1"})
    env.pop("PYTHONPATH", None)
    port = urllib.parse.urlparse(URL).port or 8189
    args = [CFG["comfy_python"], "-s", "main.py", "--listen", "127.0.0.1", "--port", str(port)] + CFG.get("comfy_extra_args", [])
    if CFG.get("comfy_hidden", True):     # no console window; ComfyUI still writes its own log file
        subprocess.Popen(args, cwd=CFG["comfy_dir"], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0)
    else:
        subprocess.Popen(args, cwd=CFG["comfy_dir"], env=env, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    t0 = time.time()
    while time.time() - t0 < CFG.get("comfy_start_timeout", 300):
        time.sleep(3)
        if comfy_up():
            log("ComfyUI is up after %.0fs" % (time.time() - t0))
            return
    raise RuntimeError("ComfyUI did not start - check its console window")

def comfy_free():
    try:
        http("POST", "/free", {"unload_models": True, "free_memory": True}, timeout=30)
    except Exception as e:
        log("comfy free failed: %s" % e)

def short_err(blob):
    try:
        d = json.loads(blob) if isinstance(blob, (bytes, str)) else blob
    except Exception:
        return str(blob)[:400]
    parts = []
    e = d.get("error")
    if isinstance(e, dict):
        parts.append(e.get("message", "") + (" " + e.get("details", "") if e.get("details") else ""))
    for nid, ne in (d.get("node_errors") or {}).items():
        for er in ne.get("errors", []):
            parts.append("%s(%s): %s %s" % (nid, ne.get("class_type"), er.get("message"), er.get("details", "")))
    return " | ".join(p.strip() for p in parts if p.strip())[:600] or str(d)[:400]

def queue(graph):
    try:
        r = http("POST", "/prompt", {"prompt": graph, "client_id": CLIENT_ID})
    except urllib.error.HTTPError as e:
        raise RuntimeError(short_err(e.read()))
    if r.get("node_errors"):
        raise RuntimeError(short_err(r))
    return r["prompt_id"]

def wait(pid, timeout):
    imgs = (wait_outputs(pid, timeout).get("out") or {}).get("images")
    if not imgs:
        raise RuntimeError("finished without an image")
    return imgs[0]

def wait_outputs(pid, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = http("GET", "/history/" + pid)
        if h and pid in h:
            e = h[pid]
            st = e.get("status") or {}
            if st.get("status_str") == "error":
                msg = "execution error"
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        d = m[1]
                        msg = "%s: %s" % (d.get("node_type"), str(d.get("exception_message", "")).strip())
                raise RuntimeError(msg[:600])
            if st.get("completed", True) or e.get("outputs"):
                return e.get("outputs") or {}
        time.sleep(1)
    raise TimeoutError("no result after %ds" % timeout)

def fetch_image(info):
    q = urllib.parse.urlencode({"filename": info["filename"], "subfolder": info.get("subfolder", ""), "type": info.get("type", "temp")})
    return http("GET", "/view?" + q, timeout=120, raw=True)

def upload_image(path):
    name = "comfort_" + re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(path))
    with open(path, "rb") as f:
        data = f.read()
    b = uuid.uuid4().hex
    body = (("--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n" % b).encode()
            + ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\nContent-Type: application/octet-stream\r\n\r\n" % (b, name)).encode()
            + data + ("\r\n--%s--\r\n" % b).encode())
    req = urllib.request.Request(URL + "/upload/image", data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + b)
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read())
    return (res["subfolder"] + "/" + res["name"]) if res.get("subfolder") else res["name"]

# ---------------------------------------------------------------- sizes
def parse_aspect(a):
    if isinstance(a, (int, float)):
        return float(a)
    if isinstance(a, (list, tuple)):
        return a[0] / a[1]
    a = str(a).strip()
    if ":" in a:
        x, y = a.split(":")
        return float(x) / float(y)
    if "x" in a.lower():
        x, y = a.lower().split("x")
        return float(x) / float(y)
    return float(a)

def gen_dims(aspect, mp, mult=16):
    a = parse_aspect(aspect)
    w = math.sqrt(float(mp) * 1e6 * a)
    h = w / a
    r = lambda v: max(mult, int(v / mult + 0.5) * mult)
    return r(w), r(h)

def parse_wh(v):
    if v in (None, "", "none", "None"):
        return None
    if isinstance(v, (list, tuple)):
        return int(v[0]), int(v[1])
    m = re.match(r"^\s*(\d+)\s*[x*,]\s*(\d+)\s*$", str(v))
    if not m:
        raise ValueError("bad size '%s' (use WxH)" % v)
    return int(m.group(1)), int(m.group(2))

def parse_loras(v):
    out = []
    for part in [p for p in re.split(r"[;|]", v or "") if p.strip()]:
        name, _, st = part.strip().rpartition(":")
        if not name:
            name, st = st, "1"
        out.append((name, float(st)))
    return out

# ---------------------------------------------------------------- graphs (API format)
def g_krea(prompt, seed, w, h, s):
    k = CFG["krea"]
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": k["unet"], "weight_dtype": "default"}},
        "enh": {"class_type": "ComfyUI-Krea2T-Enhancer", "inputs": {"model": ["unet", 0], "enabled": True, "strength": k.get("enhancer_strength", 1.5), "debug": False}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": k["clip"], "type": "krea2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": k["vae"]}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["clip", 0]}},
        "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos", 0]}},
        "lat": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
    }
    model = ["enh", 0]
    loras = [tuple(x) for x in k.get("loras", [])] + parse_loras(s.get("lora"))
    for i, (name, st) in enumerate(loras):
        g["lora%d" % i] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": name, "strength_model": float(st)}}
        model = ["lora%d" % i, 0]
    common = {"seed": seed, "sampler_mode": "standard", "bongmath": True, "model": model, "positive": ["pos", 0], "negative": ["neg", 0]}
    p1 = k["pass1"]
    steps = int(s.get("steps") or p1["steps"])
    g["s1"] = {"class_type": "ClownsharKSampler_Beta", "inputs": dict(common, eta=p1["eta"], sampler_name=p1["sampler_name"], scheduler=p1["scheduler"], steps=steps, steps_to_run=-1, denoise=1.0, cfg=p1["cfg"], latent_image=["lat", 0])}
    last = ["s1", 1]
    p2 = k.get("pass2") or {}
    if p2.get("enabled", True) and str(s.get("pass2", "on")).lower() not in ("off", "0", "false", "no"):
        g["s2"] = {"class_type": "ClownsharKSampler_Beta", "inputs": dict(common, eta=p2["eta"], sampler_name=p2["sampler_name"], scheduler=p2["scheduler"], steps=p2["steps"], steps_to_run=int(math.ceil(p2["denoise"] * p2["steps"])), denoise=p2["denoise"], cfg=p2["cfg"], latent_image=["s1", 0])}
        last = ["s2", 1]
    g["dec"] = {"class_type": "VAEDecode", "inputs": {"samples": last, "vae": ["vae", 0]}}
    return g, ["dec", 0]

def g_edit(prompt, seed, w, h, s):
    k = CFG["edit"]
    img = s["_uploaded"]
    g = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": k["unet"], "weight_dtype": "default"}},
        "lora": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": k["lora"], "strength_model": float(k.get("lora_strength", 1))}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": k["clip"], "type": "krea2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": k["vae"]}},
        "img": {"class_type": "LoadImage", "inputs": {"image": img}},
        "venc": {"class_type": "VAEEncode", "inputs": {"pixels": ["img", 0], "vae": ["vae", 0]}},
        "lat": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "patch": {"class_type": "Krea2EditModelPatch", "inputs": {"model": ["lora", 0], "source_latent": ["venc", 0], "ref_boost": float(s.get("boost") or k.get("ref_boost", 4)), "ref_boost_a": 1.0, "fit_mode": "fit", "vae": ["vae", 0], "source_image": ["img", 0], "target_latent": ["lat", 0]}},
        "pos": {"class_type": "Krea2EditGroundedEncode", "inputs": {"clip": ["clip", 0], "prompt": prompt, "image": ["img", 0], "grounding_px": int(k.get("grounding_px", 768)), "system_prompt": ""}},
        "neg": {"class_type": "Krea2EditGroundedEncode", "inputs": {"clip": ["clip", 0], "prompt": "", "image": ["img", 0], "grounding_px": int(k.get("grounding_px", 768)), "system_prompt": ""}},
        "ks": {"class_type": "KSampler", "inputs": {"model": ["patch", 0], "seed": seed, "steps": int(s.get("steps") or k.get("steps", 10)), "cfg": float(k.get("cfg", 1)), "sampler_name": k.get("sampler_name", "euler"), "scheduler": k.get("scheduler", "simple"), "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["lat", 0], "denoise": 1.0}},
        "dec": {"class_type": "VAEDecode", "inputs": {"samples": ["ks", 0], "vae": ["vae", 0]}},
    }
    # style LoRAs (#lora) chained after the identity LoRA (2026-10-26)
    model = ["lora", 0]
    for i, (name, st) in enumerate(parse_loras(s.get("lora"))):
        g["slora%d" % i] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": name, "strength_model": float(st)}}
        model = ["slora%d" % i, 0]
    g["patch"]["inputs"]["model"] = model
    return g, ["dec", 0]

BUILDERS = {"krea": g_krea, "edit": g_edit}

def g_i2p(image_name, text, seed):
    k = CFG["i2p"]
    return {
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": k["clip"], "type": "krea2", "device": "default"}},
        "img": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "gen": {"class_type": "TextGenerate", "inputs": {"clip": ["clip", 0], "prompt": text, "image": ["img", 0], "max_length": int(k.get("max_length", 512)),
                "sampling_mode": "on", "sampling_mode.temperature": float(k.get("temperature", 0.7)), "sampling_mode.top_k": 64, "sampling_mode.top_p": 0.95,
                "sampling_mode.min_p": 0.05, "sampling_mode.repetition_penalty": 1.05, "sampling_mode.seed": int(seed), "thinking": bool(k.get("thinking", True)), "use_default_template": True}},
        "txt": {"class_type": "PreviewAny", "inputs": {"source": ["gen", 0]}},
    }

I2P_CACHE = {}
def image_to_prompt(path, hint, seed):
    key = (path, hint)
    if key in I2P_CACHE:
        return I2P_CACHE[key]
    k = CFG["i2p"]
    up = path
    try:
        from PIL import Image
        with Image.open(path) as im:
            mp = float(k.get("max_mp", 1.5)) * 1e6
            if im.width * im.height > mp:
                f = math.sqrt(mp / (im.width * im.height))
                up = P("inputs", "_i2p_" + os.path.splitext(os.path.basename(path))[0] + ".png")
                im.convert("RGB").resize((int(im.width * f), int(im.height * f)), Image.LANCZOS).save(up)
    except Exception as e:
        log("i2p resize skipped: %s" % e)
    text = k["system"] + k.get("join", "\n\nCreative direction: ") + (hint or "")
    out = wait_outputs(queue(g_i2p(upload_image(up), text, seed)), CFG.get("image_timeout", 900))
    t = (out.get("txt") or {}).get("text")
    if not t:
        raise RuntimeError("image-to-prompt returned no text")
    t = t[0] if isinstance(t, (list, tuple)) else t
    t = re.sub(r"^\s*(\*\*[^*\n]{0,60}\*\*|here is[^\n]{0,80}:|prompt\s*:)\s*", "", str(t).strip(), flags=re.I).strip().strip('"').strip()
    if not t:
        raise RuntimeError("image-to-prompt returned empty text")
    I2P_CACHE[key] = t
    return t

def finish(g, ref, gw, gh, final, upscale):
    if final:
        fw, fh = final
        if (fw > gw or fh > gh) and upscale:
            g["upm"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": upscale}}
            g["up"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["upm", 0], "image": ref}}
            ref = ["up", 0]
        g["fit"] = {"class_type": "ImageScale", "inputs": {"image": ref, "upscale_method": "lanczos", "width": fw, "height": fh, "crop": "center"}}
        ref = ["fit", 0]
    g["out"] = {"class_type": "PreviewImage", "inputs": {"images": ref}}
    return g

# ---------------------------------------------------------------- job parsing
KEYS = {"name", "wf", "preset", "style", "n", "seed", "size", "aspect", "mp", "final", "upscale", "image", "label", "lora", "steps", "boost", "pass2", "i2p"}

def parse_txt(text):
    head, cur, items = {}, {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("##"):
            continue
        if line.startswith("#"):
            key, _, val = line[1:].partition(" ")
            key, val = key.strip().lower(), val.strip()
            if key not in KEYS:
                raise ValueError("unknown header #%s" % key)
            if key == "name":
                head["name"] = val
            else:
                cur[key] = val
            continue
        over = {}
        m = re.match(r"^\[([^\]]*)\]\s*(.*)$", line)
        if m:
            for tok in m.group(1).split():
                k2, _, v2 = tok.partition("=")
                if k2.lower() not in KEYS:
                    raise ValueError("unknown option [%s]" % k2)
                over[k2.lower()] = v2
            line = m.group(2)
        items.append(dict(cur, **over, prompt=line))
    head["items"] = items
    return head

def parse_json(d):
    base = {k: v for k, v in d.items() if k in KEYS and k != "name"}
    items = []
    for p in d.get("prompts", []):
        items.append(dict(base, prompt=p) if isinstance(p, str) else dict(base, **p))
    return {"name": d.get("name"), "items": items}

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")

def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())

def gallery_jobs():
    """[(job, mtime, [image files])] newest first."""
    d = P("out")
    out = []
    for j in os.listdir(d) if os.path.isdir(d) else []:
        p = os.path.join(d, j)
        if os.path.isdir(p):
            files = sorted(f for f in os.listdir(p) if f.lower().endswith(IMG_EXT) and not f.startswith("_"))
            if files:
                out.append((j, os.path.getmtime(p), files))
    return sorted(out, key=lambda x: -x[1])

STOP = {"the", "picture", "image", "img", "gallery", "named", "called", "from", "one", "file", "pic", "photo",
        "first", "second", "third", "fourth", "fifth", "last", "number", "latest", "and", "with"}

def _pick_file(files, ref, job=""):
    m = re.search(r"(\d{2}-\d+)", ref)
    if m:
        hit = [f for f in files if f.startswith(m.group(1))]
        if hit:
            return hit[0]
    words = [w for w in re.findall(r"[a-z]{3,}", ref.lower()) if w not in STOP and w not in job.lower()]
    pool = files
    if words:
        scored = [(sum(1 for w in words if w in f.lower()), f) for f in files]
        top = max(s for s, _ in scored)
        if top > 0:
            pool = [f for s, f in scored if s == top]
    m = re.search(r"(?:#|image\s*|img\s*|number\s*|no\.?\s*)(\d+)\s*$", ref.lower())
    if m and 1 <= int(m.group(1)) <= len(pool):
        return pool[int(m.group(1)) - 1]
    for w, i in {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "last": -1}.items():
        if re.search(r"\b%s\b" % w, ref.lower()) and (i < len(pool) if i >= 0 else True):
            return pool[i]
    return pool[0]

def resolve_gallery(ref):
    """Loose gallery reference -> absolute path. 'pond wide 3', 'rez forest 01-2', 'latest', 'job/file.png'."""
    import difflib
    jobs = gallery_jobs()
    if not jobs:
        raise FileNotFoundError("the gallery is empty")
    r = str(ref).strip().strip('"').replace("\\", "/")
    if re.fullmatch(r"(latest|newest|last|most recent)( (image|picture|one|result))?", r.lower()):
        j, _, files = jobs[0]
        return os.path.join(P("out", j), files[0])
    job_part, _, file_part = r.partition("/")
    target = _norm(re.sub(r"\b(the|picture|image|pic|photo|in|gallery|named|called|from|of|one|file)\b", " ", job_part.lower()))
    best, score = None, 0.0
    for j, _, files in jobs:
        nj = _norm(j)
        s = difflib.SequenceMatcher(None, target, nj).ratio()
        if nj and (nj in target or target in nj):
            s = max(s, 0.9)
        if s > score:
            best, score = (j, files), s
    if not best or score < 0.6:
        words = [w for w in re.findall(r"[a-z]{3,}", r.lower()) if w not in ("the", "picture", "image", "gallery", "named", "called", "from", "one", "file")]
        cands = []
        for j, _, files in jobs:
            for f in files:
                hay = (j + " " + f).lower()
                hit = sum(1 for w in words if w in hay)
                if words and hit / len(words) >= 0.5:
                    cands.append((hit, j, f))
        if cands:
            top = max(h for h, _, _ in cands)
            pool = [(j, f) for h, j, f in cands if h == top]
            j0, f0 = pool[0]
            same = [f for j, f in pool if j == j0]
            return os.path.join(P("out", j0), _pick_file(same, r, j0) if len(same) > 1 else f0)
        raise FileNotFoundError("no gallery image matches '%s'. Recent jobs: %s" % (ref, ", ".join(j for j, _, _ in jobs[:12])))
    j, files = best
    if file_part:
        hit = [f for f in files if f == file_part] or [f for f in files if _norm(file_part) in _norm(f)]
        f = hit[0] if hit else _pick_file(files, file_part, j)
    else:
        f = _pick_file(files, r, j)
    return os.path.join(P("out", j), f)

def find_file(p):
    for c in (p, P("inputs", p), P("out", p), P(p)):
        if os.path.isfile(c):
            return c
    try:
        return resolve_gallery(p)
    except FileNotFoundError as e:
        raise FileNotFoundError("image not found: %s (not in inputs\\ or out\\; %s)" % (p, e))

def is_none(v):
    return v is None or str(v).strip().lower() in ("", "none", "off")

def resolve(it):
    s = {}
    pr = it.get("preset")
    if not is_none(pr):
        if pr not in PRESETS:
            raise ValueError("unknown preset '%s' (see presets.json)" % pr)
        s.update(PRESETS[pr])
    for k, v in it.items():
        if k != "preset" and v is not None:
            s[k] = v
    s["wf"] = s.get("wf") or "krea"
    if s["wf"] not in BUILDERS and s["wf"] != "i2p":
        raise ValueError("unknown wf '%s'" % s["wf"])
    styles = [] if is_none(s.get("style")) else [x.strip() for x in str(s["style"]).split(",") if x.strip()]
    tails = []
    for st in styles:
        if st not in STYLES:
            raise ValueError("unknown style '%s' (see styles.json)" % st)
        tails.append(STYLES[st])
    s["_tails"] = tails
    s["full_prompt"] = ", ".join([s["prompt"].rstrip(" ,.")] + tails)
    src = s.get("i2p") if not is_none(s.get("i2p")) else (s.get("image") if s["wf"] == "i2p" else None)
    if s["wf"] == "i2p" and is_none(src):
        raise ValueError("wf i2p needs #i2p IMAGE")
    if not is_none(src):
        s["_i2p_path"] = find_file(str(src))
    if s["wf"] == "edit":
        if is_none(s.get("image")):
            raise ValueError("edit needs #image")
        s["_image_path"] = find_file(str(s["image"]))
    size = parse_wh(s.get("size"))
    if size:
        w, h = size
    elif s["wf"] == "edit" and is_none(s.get("aspect")):
        from PIL import Image
        with Image.open(s["_image_path"]) as im:
            iw, ih = im.size
        w, h = gen_dims(iw / ih, s.get("mp") or CFG["edit"].get("mp", 1.0))
    else:
        w, h = gen_dims(s.get("aspect") or "1:1", s.get("mp") or 1.0)
    s["w"], s["h"] = w, h
    s["final_wh"] = parse_wh(None if is_none(s.get("final")) else s.get("final"))
    s["upscale_model"] = None if str(s.get("upscale", "")).lower() in ("none", "off") else (s.get("upscale") or CFG.get("default_upscale_model"))
    s["n"] = int(s.get("n") or 1)
    s["seed"] = None if is_none(s.get("seed")) or str(s.get("seed")).lower() == "random" else int(s["seed"])
    return s

def slug(text, label=None):
    if label:
        return re.sub(r"[^A-Za-z0-9_-]+", "_", label)[:40]
    words = [w for w in re.findall(r"[A-Za-z0-9]+", text.lower()) if w not in ("a", "an", "the", "of", "single", "with", "and")]
    return "-".join(words[:3])[:28] or "img"

# ---------------------------------------------------------------- outputs
def save_png(data, path, meta):
    try:
        from PIL import Image, PngImagePlugin
        import io
        im = Image.open(io.BytesIO(data))
        info = PngImagePlugin.PngInfo()
        info.add_text("comfort", json.dumps(meta))
        im.save(path, pnginfo=info, compress_level=6)
    except Exception:
        with open(path, "wb") as f:
            f.write(data)

def contact_sheet(outdir, rows):
    rows = [r for r in rows if r.get("file")]
    if not rows:
        return None
    from PIL import Image, ImageDraw
    cell = 300 if len(rows) <= 20 else 220
    cols = min(5, len(rows))
    nrows = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, nrows * (cell + 18)), (40, 40, 44))
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows):
        with Image.open(os.path.join(outdir, r["file"])) as im:
            im = im.convert("RGB")
            im.thumbnail((cell - 8, cell - 8))
            x, y = (i % cols) * cell, (i // cols) * (cell + 18)
            sheet.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
            d.text((x + 6, y + cell + 2), r["id"], fill=(235, 235, 235))
    path = os.path.join(outdir, "_sheet.jpg")
    sheet.save(path, quality=82)
    return "_sheet.jpg"

def unique_dir(name):
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "job"
    d, i = P("out", base), 2
    if os.path.isdir(d) and not os.path.exists(os.path.join(d, "_done.txt")):   # Justice 2026-10-27: an interrupted run of
        return d                                # this same job (Comfort restarted): reuse its folder, keep the job's name
    while os.path.exists(d):
        d, i = P("out", "%s_%d" % (base, i)), i + 1
    os.makedirs(d)
    return d

# ---------------------------------------------------------------- model downloads (inbox {"download": [...]})
def download_models(items, name):
    """items: [{"url": ..., "dest": "vae/file.safetensors"}]; dest is relative to ComfyUI\\models.
    Resumes from .part files, skips files that are already there, reports in out\\NAME\\_done.txt."""
    models = os.path.realpath(os.path.join(CFG["comfy_dir"], "models"))
    outdir = unique_dir(name)
    lines, ok = [], True
    for i, it in enumerate(items, 1):
        rel = str(it.get("dest", ""))
        dest = os.path.realpath(os.path.join(models, rel))
        if not dest.startswith(models + os.sep):
            ok = False; lines.append("ERR %s: outside the models folder" % rel); continue
        if os.path.exists(dest):
            lines.append("HAVE %s %.2f GB" % (rel, os.path.getsize(dest) / 1e9)); continue
        label = os.path.basename(dest)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            part = dest + ".part"
            have = os.path.getsize(part) if os.path.exists(part) else 0
            hdr = {"User-Agent": "Comfort/1.0"}
            if have:
                hdr["Range"] = "bytes=%d-" % have
            with urllib.request.urlopen(urllib.request.Request(it["url"], headers=hdr), timeout=60) as r:
                if have and r.status != 206:
                    have = 0
                cr = r.headers.get("Content-Range", "")
                total = int(cr.rsplit("/", 1)[1]) if "/" in cr and cr.rsplit("/", 1)[1].isdigit() else int(r.headers.get("Content-Length") or 0) + have
                got, last = have, 0
                with open(part, "ab" if have else "wb") as f:
                    while True:
                        chunk = r.read(8 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if time.time() - last > 2:
                            last = time.time()
                            set_status("downloading %d/%d %s %.0f%% (%.2f/%.2f GB)" % (i, len(items), label, 100.0 * got / max(total, 1), got / 1e9, total / 1e9))
            if total and os.path.getsize(part) != total:
                raise RuntimeError("incomplete: %d of %d bytes (send the job again to resume)" % (os.path.getsize(part), total))
            os.replace(part, dest)
            lines.append("OK %s %.2f GB" % (rel, os.path.getsize(dest) / 1e9))
            log("downloaded %s" % dest)
        except Exception as e:
            ok = False
            lines.append("ERR %s: %s" % (rel, str(e)[:300]))
            log("download %s failed: %s" % (rel, e))
    head = "%s downloads job=%s" % ("OK" if ok else "FAILED", os.path.basename(outdir))
    with open(os.path.join(outdir, "_done.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join([head] + lines) + "\n")
    log(head)
    set_status("done %s -> %s" % (head.split()[0], os.path.basename(outdir)))
    return ok


# ---------------------------------------------------------------- run
def run_job(job, default_name):
    with JOB_LOCK:
        return _run_job(job, default_name)

def _run_job(job, default_name):
    t0 = time.time()
    name = job.get("name") or default_name
    specs = [resolve(it) for it in job["items"]]
    if not specs:
        raise ValueError("no prompts in job")
    outdir = unique_dir(name)
    jname = os.path.basename(outdir)
    runs = []
    for idx, s in enumerate(specs, 1):
        for k in range(1, s["n"] + 1):
            seed = (s["seed"] + k - 1) if s["seed"] is not None else random.randint(1, 2 ** 50)
            runs.append({"id": "%02d-%d" % (idx, k), "spec": s, "seed": seed})
    set_status("running %s 0/%d" % (jname, len(runs)))
    log("job %s: %d images" % (jname, len(runs)))
    ensure_comfy()
    for s in specs:
        if s.get("_i2p_path"):
            try:
                set_status("image-to-prompt %s" % jname)
                hint = "" if s["prompt"].strip() in ("-", "") else s["prompt"]
                s["derived"] = image_to_prompt(s["_i2p_path"], hint, int(CFG["i2p"].get("seed", 0)))
                s["full_prompt"] = ", ".join([s["derived"].rstrip(" ,.")] + s["_tails"])
            except Exception as e:
                s["i2p_error"] = "image-to-prompt: %s" % e
    uploaded = {}
    for r in runs:
        s = r["spec"]
        if s.get("i2p_error"):
            r["error"] = s["i2p_error"]
            continue
        if s["wf"] == "i2p":
            r["prompt_only"] = True
            continue
        try:
            if s["wf"] == "edit":
                if s["_image_path"] not in uploaded:
                    uploaded[s["_image_path"]] = upload_image(s["_image_path"])
                s["_uploaded"] = uploaded[s["_image_path"]]
            g, ref = BUILDERS[s["wf"]](s["full_prompt"], r["seed"], s["w"], s["h"], s)
            finish(g, ref, s["w"], s["h"], s["final_wh"], s["upscale_model"])
            r["pid"] = queue(g)
        except Exception as e:
            r["error"] = str(e)
    rows = []
    for i, r in enumerate(runs, 1):
        s = r["spec"]
        row = {"id": r["id"], "seed": r["seed"], "wf": s["wf"], "preset": s.get("preset"), "size": "%dx%d" % (s["w"], s["h"]),
               "final": "%dx%d" % s["final_wh"] if s["final_wh"] else None, "prompt": s.get("derived") or s["prompt"], "style": s.get("style"),
               "image": s.get("image")}
        if r.get("prompt_only"):
            row["prompt_only"] = True
        elif "pid" in r:
            try:
                t1 = time.time()
                info = wait(r["pid"], CFG.get("image_timeout", 900))
                fname = "%s_%s.png" % (r["id"], slug(s.get("derived") or s["prompt"], s.get("label")))
                save_png(fetch_image(info), os.path.join(outdir, fname), {"prompt": s["full_prompt"], "seed": r["seed"], "wf": s["wf"]})
                row.update(file=fname, secs=round(time.time() - t1, 1))
            except Exception as e:
                row["error"] = str(e)
        else:
            row["error"] = r.get("error", "not queued")
        rows.append(row)
        set_status("running %s %d/%d" % (jname, i, len(runs)))
    with open(os.path.join(outdir, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"job": jname, "rows": rows, "full_prompts": {r["id"]: r["spec"]["full_prompt"] for r in runs}}, f, indent=1)
    try:
        sheet = contact_sheet(outdir, rows)
    except Exception as e:
        sheet = None
        log("sheet failed: %s" % e)
    with open(os.path.join(outdir, "_prompts.txt"), "w", encoding="utf-8") as f:
        for r in runs:
            f.write("%s: %s\n\n" % (r["id"], r["spec"]["full_prompt"]))
    ok = sum(1 for r in rows if r.get("file") or r.get("prompt_only"))
    lines = ["%s %d/%d  job=%s  %.0fs  dir=%s" % ("OK" if ok == len(rows) else "PARTIAL" if ok else "FAILED", ok, len(rows), jname, time.time() - t0, outdir)]
    if sheet:
        lines.append("sheet=" + sheet)
    for r in rows:
        if r.get("prompt_only"):
            lines.append("%s  prompt only -> _prompts.txt" % r["id"])
        elif r.get("file"):
            lines.append("%s  %s%s  seed=%s" % (r["file"], r["size"], (">" + r["final"]) if r["final"] else "", r["seed"]))
        else:
            lines.append("ERR %s: %s" % (r["id"], r.get("error")))
    with open(os.path.join(outdir, "_done.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(lines[0])
    set_status("done %s -> %s" % (lines[0].split()[0], jname))
    return outdir, ok == len(rows)

def reload_data():
    global CFG, PRESETS, STYLES
    CFG = load_json(os.environ.get("COMFORT_CONFIG", P("config.json")))
    PRESETS = load_json(P("presets.json"))
    STYLES = load_json(P("styles.json"))

def filmcraft_build(cut, name):
    """Run FilmCraft's fc.py build <cut list> on Windows (Justice 2026-10-25: the Linux device shell kills builds over 3 min).
    cut = cut list path relative to the FilmCraft folder, e.g. projects/ciudad_fantasma/ciudad_fantasma.txt. Result -> out\<name>\_done.txt."""
    fdir = CFG.get("filmcraft_dir") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "FilmCraft")
    cut = cut.replace("/", os.sep)
    if not cut.lower().endswith(".txt") or ".." in cut or os.path.isabs(cut):
        raise ValueError("filmcraft_build needs a .txt cut list inside the FilmCraft folder")
    outdir = P("out", name)
    os.makedirs(outdir, exist_ok=True)
    set_status("running filmcraft build %s" % name)
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-5] + ".exe"):
        exe = exe[:-5] + ".exe"           # pythonw has no stdout; fc.py prints its result line
    t0 = time.time()
    r = subprocess.run([exe, os.path.join(fdir, "fc.py"), "build", cut], cwd=fdir, capture_output=True, text=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    lines = (r.stdout or "").strip().splitlines()
    line = lines[-1] if lines else ""
    ok = r.returncode == 0 and line.startswith("ok")
    with open(os.path.join(outdir, "_done.txt"), "w", encoding="utf-8") as f:
        f.write("%s filmcraft job=%s %.0fs\n%s\n%s\n" % ("OK" if ok else "FAILED", name, time.time() - t0, line, (r.stderr or "")[-1500:]))
    log("%s filmcraft %s %.0fs: %s" % ("OK" if ok else "FAILED", name, time.time() - t0, line or (r.stderr or "")[-300:]))
    return ok

def run_file(path, move=False):
    reload_data()
    base = os.path.splitext(os.path.basename(path))[0]
    ok = False
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        data = json.loads(text) if path.lower().endswith(".json") else None
        if isinstance(data, dict) and data.get("workflow"):
            import comfort_flows
            data.setdefault("name", base)
            _, ok = comfort_flows.run_flow(data)
        elif isinstance(data, dict) and data.get("agent"):
            import comfort_agent
            a = comfort_agent.Agent()
            a._run(str(data["agent"]), data.get("attachments") or [])
            os.makedirs(P("agent_logs"), exist_ok=True)
            with open(P("agent_logs", base + ".txt"), "w", encoding="utf-8") as f:
                for it in a.display:
                    f.write("[%s] %s%s\n" % (it["kind"], it["text"], ("  " + " ".join(it["images"])) if it["images"] else ""))
            ok = not any(it["kind"] == "error" for it in a.display)
        elif isinstance(data, dict) and data.get("make_video"):
            import comfort_agent
            args = dict(data["make_video"])
            args.setdefault("name", base)
            comfort_agent.t_make_video(**args)
            ok = True
        elif isinstance(data, dict) and data.get("llm_benchmark"):
            import comfort_agent
            comfort_agent.benchmark()
            ok = True
        elif isinstance(data, dict) and data.get("download"):
            ok = download_models(data["download"], data.get("name") or base)
        elif isinstance(data, dict) and data.get("filmcraft_build"):
            ok = filmcraft_build(str(data["filmcraft_build"]), data.get("name") or base)
        elif isinstance(data, dict) and data.get("convert_workflows"):
            import comfort_flows
            log("convert: %s" % comfort_flows.convert_workflows(data.get("only")))
            ok = True
        else:
            job = parse_json(data) if data is not None else parse_txt(text)
            _, ok = run_job(job, base)
    except Exception as e:
        log("job %s failed: %s" % (base, e))
        set_status("error %s: %s" % (base, str(e)[:300]))
        with open(P("jobs", "failed", base + ".error.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
    if move:
        dest = P("jobs", "done" if ok else "failed", os.path.basename(path))
        if os.path.exists(dest):
            dest = dest + "." + time.strftime("%H%M%S")
        shutil.move(path, dest)

def claim_inbox(owner):
    lock = P("watcher.lock")
    try:
        with open(lock, encoding="utf-8") as f:
            who, ts = f.read().split("|")
        if who != owner and time.time() - float(ts) < 30:
            return False
    except Exception:
        pass
    with open(lock, "w", encoding="utf-8") as f:
        f.write("%s|%f" % (owner, time.time()))
    return True

_OVERSEER = {"t": 0.0}

def overseer_tick():
    """Star Trek OVERSEER (Justice 2026-10-27): the local AI checks every picture and shot, re-makes bad ones, keeps the
    queue fed and builds the edits, so production never waits on Claude. Runs ..\\Overseer\\overseer.py tick between
    jobs and every 20 s when idle (no-op when ..\\Overseer\\PAUSE exists). See Star Trek\\README.txt."""
    ov = os.path.normpath(P("..", "Overseer", "overseer.py"))
    if not os.path.exists(ov) or time.time() - _OVERSEER["t"] < 20:
        return
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe") and os.path.exists(exe[:-5] + ".exe"):
        exe = exe[:-5] + ".exe"
    try:
        r = subprocess.run([exe, ov, "tick"], cwd=os.path.dirname(ov), capture_output=True, text=True, timeout=1800,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = (r.stdout or "").strip().splitlines()
        if r.returncode:
            log("overseer FAILED: %s" % (r.stderr or "")[-300:])
        elif out:
            log("overseer: %s" % out[-1][:300])
    except Exception as e:
        log("overseer: %s" % e)
    _OVERSEER["t"] = time.time()

def process_inbox_once(owner):
    if not claim_inbox(owner):
        return False
    overseer_tick()
    reload_data()
    jobs = sorted(f for f in os.listdir(P("inbox")) if f.lower().endswith((".txt", ".json")) and not f.startswith(("_", ".")))
    if not jobs:
        return False
    time.sleep(0.5)
    run_file(P("inbox", jobs[0]), move=True)
    return True

def watch():
    for d in ("inbox", "out", "inputs", os.path.join("jobs", "done"), os.path.join("jobs", "failed")):
        os.makedirs(P(d), exist_ok=True)
    log("Comfort watching %s  (ComfyUI %s)" % (P("inbox"), URL))
    beat = 0
    code_mtime = os.path.getmtime(os.path.abspath(__file__))
    while True:
        for flag, code in (("_restart", 3), ("_stop", 0)):
            if os.path.exists(P("inbox", flag)):
                os.remove(P("inbox", flag))
                log("%s requested" % flag[1:])
                set_status("stopped (%s)" % flag[1:])
                sys.exit(code)
        if os.path.getmtime(os.path.abspath(__file__)) != code_mtime:
            log("comfort.py changed - restarting")
            sys.exit(3)
        try:
            if process_inbox_once("watch-%d" % os.getpid()):
                beat = 0
                continue
            if time.time() - beat > 10:
                set_status("idle (watching)")
                beat = time.time()
        except Exception as e:
            log("watch loop error: %s" % e)
        time.sleep(1)

def list_presets():
    for k, v in PRESETS.items():
        if k.startswith("_"):
            continue
        w, h = parse_wh(v.get("size")) or gen_dims(v.get("aspect", "1:1"), v.get("mp", 1.0))
        fin = v.get("final")
        print("%-14s %5dx%-5d%s  style=%s  %s" % (k, w, h, (" -> %sx%s" % tuple(fin)) if fin else "", v.get("style", "-"), v.get("note", "")))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if cmd == "watch":
        watch()
    elif cmd == "run" and len(sys.argv) > 2:
        run_file(sys.argv[2])
    elif cmd == "presets":
        list_presets()
    else:
        print(__doc__)
