"""Comfort workflow engine: run ANY saved ComfyUI workflow with ANY parameter changed.

Workflows are converted to ComfyUI's API format by ComfyUI's own frontend (loaded in a hidden
Edge/Chrome window), so subgraphs, Set/Get nodes, Anything Everywhere and bypassed groups come out
exactly as the UI would queue them. Exports live in <comfy_dir>/user/default/comfort_api/.
"""
import asyncio, json, os, random, re, shutil, subprocess, tempfile, time

import comfort as C

SKIP_CLASSES = {"easy showAnything", "PreviewAny", "Note", "MarkdownNote", "FancyTimerNode",
                "SystemNotification|pysssss", "Image Comparer (rgthree)"}
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
VID_EXT = (".mp4", ".webm", ".mov", ".mkv")


# ---------------------------------------------------------------- registry
def api_dir():
    return os.path.join(C.CFG["comfy_dir"], "user", "default", "comfort_api")

def list_workflows():
    d, out = api_dir(), []
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".api.json"):
                out.append(os.path.relpath(os.path.join(root, f), d)[:-len(".api.json")].replace("\\", "/"))
    return sorted(out, key=str.lower)

def ui_workflows():
    d, out = os.path.join(C.CFG["comfy_dir"], "user", "default", "workflows"), []
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith(".json"):
                out.append(os.path.relpath(os.path.join(root, f), d)[:-5].replace("\\", "/"))
    return sorted(out, key=str.lower)

def guide(name):
    for n in (name, os.path.basename(name)):
        p = C.P("guides", n + ".md")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
    return None

def summary(name):
    g = guide(name) or ""
    for line in g.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200]
    return ""

def wf_path(name):
    return os.path.join(api_dir(), name.replace("/", os.sep) + ".api.json")

def load_workflow(name):
    if os.path.exists(wf_path(name)):
        return name, C.load_json(wf_path(name))
    cands = [w for w in list_workflows() if name.lower() in w.lower()]
    if len(cands) == 1:
        return cands[0], C.load_json(wf_path(cands[0]))
    raise ValueError("unknown workflow '%s'. Available: %s" % (name, "; ".join(list_workflows()) or "none - run convert first"))

def _id_key(nid):
    return [int(x) if x.isdigit() else x for x in re.split(r"[:]", str(nid))]

def nodes_with_params(g):
    """[(node_id, class, title, {input: value})] for every node that has editable (non-link) inputs."""
    rows = []
    for nid in sorted(g, key=_id_key):
        nd = g[nid]
        ct = nd.get("class_type", "")
        if ct in SKIP_CLASSES:
            continue
        params = {k: v for k, v in (nd.get("inputs") or {}).items() if not isinstance(v, list)}
        if params:
            rows.append((nid, ct, (nd.get("_meta") or {}).get("title") or ct, params))
    return rows

def describe(name, filt=None, maxlen=100):
    name, g = load_workflow(name)
    lines = []
    for nid, ct, title, params in nodes_with_params(g):
        parts = []
        for k, v in params.items():
            if isinstance(v, str):
                v1 = v.replace("\n", " ")
                parts.append('%s="%s%s"' % (k, v1[:maxlen], "..." if len(v1) > maxlen else ""))
            else:
                parts.append("%s=%s" % (k, json.dumps(v)))
        line = "%s | %s%s | %s" % (nid, title, "" if title == ct else " (%s)" % ct, "; ".join(parts))
        if not filt or filt.lower() in line.lower():
            lines.append(line)
    return name, lines


# ---------------------------------------------------------------- parameter edits
def resolve_key(g, key):
    """'46.value' | '127:116.seed' | 'POSITIVE PROMPT.value' | 'EmptyLatentImage.width' -> (node_id, input)."""
    key = key.strip()
    for nid in sorted(g, key=len, reverse=True):
        if key.startswith(nid + "."):
            return _check(g, nid, key[len(nid) + 1:])
    best, hits = 0, []
    for nid, nd in g.items():
        for label in ((nd.get("_meta") or {}).get("title") or "", nd.get("class_type", "")):
            if label and key.lower().startswith(label.lower() + "."):
                if len(label) > best:
                    best, hits = len(label), [nid]
                elif len(label) == best and nid not in hits:
                    hits.append(nid)
    if len(hits) == 1:
        return _check(g, hits[0], key[best + 1:])
    if len(hits) > 1:
        raise ValueError("'%s' matches several nodes (%s) - use the node id" % (key, ", ".join(hits)))
    raise ValueError("no node for '%s' (use 'node_id.input' from describe_workflow)" % key)

def _check(g, nid, inp):
    inputs = g[nid].get("inputs") or {}
    if inp not in inputs:
        raise ValueError("node %s (%s) has no input '%s'. Inputs: %s" % (nid, g[nid].get("class_type"), inp, ", ".join(inputs)))
    if isinstance(inputs[inp], list):
        raise ValueError("%s.%s is wired to another node, not a setting" % (nid, inp))
    return nid, inp

def coerce(v, old):
    try:
        if isinstance(old, bool):
            return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes", "on")
        if isinstance(old, int) and not isinstance(v, bool):
            return int(float(v))
        if isinstance(old, float):
            return float(v)
    except (TypeError, ValueError):
        pass
    return v


# ---------------------------------------------------------------- run
def filmcraft_add(jname, vp, trans=None):
    """<song>_vid<N>_stage60 -> append to A:\\artcraft\\FilmCraft\\projects\\<song>\\<song>.txt and queue a rebuild (filmcraft_build job)."""
    m = re.match(r"^(.+)_vid(\d+)_stage60$", jname)
    if not m:
        return
    song = m.group(1)
    fdir = C.CFG.get("filmcraft_dir") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "FilmCraft")
    cut = os.path.join(fdir, "projects", song, song + ".txt")
    if not os.path.exists(cut):
        return
    with open(cut, encoding="utf-8") as f:
        txt = f.read()
    if os.path.basename(vp).lower() in txt.lower():
        return
    has_clip = any(l.strip().startswith("clip ") for l in txt.splitlines())
    # Keep story order: insert before the first <song>_vid<M> clip with M > N (stage jobs finish in name order, so vid10 runs before vid7).
    n = int(m.group(2))
    lines = txt.splitlines()
    at = None
    for i, l in enumerate(lines):
        mm = re.search(r"_vid(\d+)_stage60\.mp4\s*$", l.strip()) if l.strip().startswith("clip ") else None
        if mm and int(mm.group(1)) > n:
            at = i - 1 if i > 0 and lines[i - 1].strip().startswith(">") else i
            break
    if at is None:
        txt = (txt if txt.endswith("\n") else txt + "\n") + (("> %s\n" % (trans or "dissolve 16")) if has_clip else "") + "clip %s\n" % vp
    elif lines[at].strip().startswith(">"):
        lines[at:at] = ["> %s" % (trans or "dissolve 16"), "clip %s" % vp]
        txt = "\n".join(lines) + "\n"
    else:
        lines[at:at] = ["clip %s" % vp, "> dissolve 16"]
        txt = "\n".join(lines) + "\n"
    with open(cut, "w", encoding="utf-8") as f:
        f.write(txt)
    job = C.P("inbox", "fc_%s.json" % song)
    if not os.path.exists(job):
        tmp = C.P("inbox", ".fc_" + song)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"filmcraft_build": "projects/%s/%s.txt" % (song, song), "name": "fc_" + song}, f)
        os.replace(tmp, job)
    C.log("filmcraft: added %s to %s, rebuild queued" % (os.path.basename(vp), song))

def run_flow(spec):
    """spec: {workflow, set:{key:value}, images:{key:path}, n, seed:'random'|'keep'|int, name, free_after}"""
    with C.JOB_LOCK:
        return _run_flow(spec)

def _run_flow(spec):
    t0 = time.time()
    C.reload_data()
    name, g0 = load_workflow(spec["workflow"])
    n = max(1, int(spec.get("n") or 1))
    seed = spec.get("seed", "random")
    explicit = set()
    for k, v in (spec.get("set") or {}).items():
        nid, inp = resolve_key(g0, k)
        g0[nid]["inputs"][inp] = coerce(v, g0[nid]["inputs"][inp])
        explicit.add((nid, inp))
    for k, v in (spec.get("raw_set") or {}).items():
        nid, _, inp = k.partition(".")
        g0[nid]["inputs"][inp] = v
        explicit.add((nid, inp))
    C.ensure_comfy()
    for k, path in (spec.get("images") or {}).items():
        nid, inp = resolve_key(g0, k)
        g0[nid]["inputs"][inp] = C.upload_image(C.find_file(str(path)))
        explicit.add((nid, inp))
    outdir = C.unique_dir(spec.get("name") or os.path.basename(name))
    jname = os.path.basename(outdir)
    C.set_status("running %s 0/%d" % (jname, n))
    C.log("flow %s: %s x%d" % (jname, name, n))
    runs = []
    for i in range(1, n + 1):
        g = json.loads(json.dumps(g0))
        seeds = {}
        if seed != "keep":
            for nid, nd in g.items():
                for inp, v in (nd.get("inputs") or {}).items():
                    if (inp in ("seed", "noise_seed", "seed_value") or inp.endswith(".seed")) and isinstance(v, int) and not isinstance(v, bool) and (nid, inp) not in explicit:
                        nd["inputs"][inp] = (int(seed) + i - 1) if re.fullmatch(r"-?\d+", str(seed)) else random.randint(1, 2 ** 32 - 1)  # 32-bit: some nodes (SeedVR2) reject bigger seeds
                        seeds["%s.%s" % (nid, inp)] = nd["inputs"][inp]
        r = {"run": i, "seeds": seeds}
        try:
            r["pid"] = C.queue(g)
        except Exception as e:
            r["error"] = str(e)
        runs.append(r)
    files, texts = [], []
    for r in runs:
        if "pid" in r:
            try:
                outs = C.wait_outputs(r["pid"], C.CFG.get("flow_timeout", 3600))
                got = []
                for nid, out in outs.items():
                    for kind, val in (out or {}).items():
                        if isinstance(val, list) and val and isinstance(val[0], dict) and "filename" in val[0]:
                            got += [(nid, kind, info) for info in val]
                        elif kind == "text" and isinstance(val, (list, tuple)):
                            texts.append("%02d %s: %s" % (r["run"], nid, " ".join(str(x) for x in val)))
                if any(info.get("type") == "output" for _, _, info in got):
                    got = [x for x in got if x[2].get("type") == "output"]
                for nid, kind, info in got:
                    fn = "%02d_%s_%s" % (r["run"], str(nid).replace(":", "-"), os.path.basename(info["filename"]))
                    with open(os.path.join(outdir, fn), "wb") as f:
                        f.write(C.fetch_image(info))
                    files.append({"file": fn, "run": r["run"], "node": nid, "kind": kind})
            except Exception as e:
                r["error"] = str(e)
        C.set_status("running %s %d/%d" % (jname, r["run"], n))
    imgs = [{"id": "%02d-%s" % (f["run"], f["node"]), "file": f["file"]} for f in files if f["file"].lower().endswith(IMG_EXT)]
    try:
        sheet = C.contact_sheet(outdir, imgs)
    except Exception as e:
        sheet = None
        C.log("sheet failed: %s" % e)
    if texts:
        with open(os.path.join(outdir, "_texts.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(texts) + "\n")
    vids = [f for f in files if f["file"].lower().endswith(VID_EXT)]
    if vids and C.CFG.get("videos_folder", True):
        # Justice 2026-10-20: every video in one folder (out\videos\<job>.mp4), its json/info in out\video_info\<job>\
        try:
            vdir, idir = C.P("out", "videos"), C.P("out", "video_info")
            os.makedirs(vdir, exist_ok=True)
            os.makedirs(idir, exist_ok=True)
            for i, f in enumerate(vids, 1):
                ext = os.path.splitext(f["file"])[1].lower()
                base = jname if len(vids) == 1 else "%s_%02d" % (jname, i)
                vp, k = os.path.join(vdir, base + ext), 2
                while os.path.exists(vp):
                    vp, k = os.path.join(vdir, "%s_%d%s" % (base, k, ext)), k + 1
                shutil.move(os.path.join(outdir, f["file"]), vp)
                f["file"] = vp
            dest, k = os.path.join(idir, jname), 2
            while os.path.exists(dest):
                dest, k = os.path.join(idir, "%s_%d" % (jname, k)), k + 1
            shutil.move(outdir, dest)
            outdir = dest
        except Exception as e:
            C.log("videos folder move failed: %s" % e)
    errs = ["ERR run %d: %s" % (r["run"], r["error"]) for r in runs if r.get("error")]
    ok = not errs and bool(files or texts)
    head = "%s %d/%d runs  job=%s  workflow=%s  %.0fs  dir=%s" % ("OK" if ok else ("PARTIAL" if files else "FAILED"),
            sum(1 for r in runs if not r.get("error")), n, jname, name, time.time() - t0, outdir)
    lines = [head] + (["sheet=" + sheet] if sheet else []) + [f["file"] for f in files] + (["texts=_texts.txt"] if texts else []) + errs
    with open(os.path.join(outdir, "_done.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    # Justice 2026-10-25: every new video also gets the concert-screen finish (RIFE 60 fps + RTX VSR 1920x1080).
    STAGE = "Stage 1080p60 (Comfort)"
    if ok and vids and C.CFG.get("auto_stage60", True) and spec.get("stage", True) is not False and name not in (STAGE, "Upscale and Interpolate (Comfort)"):
        for f in vids:
            try:
                vp = f["file"] if os.path.isabs(f["file"]) else os.path.join(outdir, f["file"])
                stem = os.path.splitext(os.path.basename(vp))[0]
                job = {"workflow": STAGE, "name": stem + "_stage60", "set": {"load.video": vp}, "free_after": True}
                if spec.get("fc_in"):
                    job["fc_in"] = spec["fc_in"]   # FilmCraft transition INTO this clip (new scene); chained clips default to dissolve 16
                tmp = C.P("inbox", ".stage_" + stem)
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(job, fh, indent=1)
                os.replace(tmp, C.P("inbox", stem + "_stage60.json"))
                C.log("queued stage60 finish for %s" % stem)
            except Exception as e:
                C.log("auto stage60 failed: %s" % e)
    # Justice 2026-10-25: every finished project clip goes straight into its song's FilmCraft edit, so he sees it in context.
    if ok and vids and name == STAGE and C.CFG.get("auto_filmcraft", True):
        try:
            filmcraft_add(jname, vids[0]["file"] if os.path.isabs(vids[0]["file"]) else os.path.join(outdir, vids[0]["file"]), spec.get("fc_in"))
        except Exception as e:
            C.log("auto filmcraft failed: %s" % e)
    with open(os.path.join(outdir, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"job": jname, "workflow": name, "set": spec.get("set"), "images": spec.get("images"),
                   "runs": [{k: v for k, v in r.items() if k != "pid"} for r in runs], "files": files}, f, indent=1)
    if spec.get("copy_to") and files:
        copy_results(outdir, files, sheet, spec["copy_to"], spec.get("copy_prefix") or "", n)
    C.log(head)
    C.set_status("done %s -> %s" % (head.split()[0], jname))
    if spec.get("free_after", C.CFG.get("free_after_job", False)):
        C.comfy_free()
    return outdir, ok


def copy_results(outdir, files, sheet, dest, prefix, n):
    """Copy a job's results into a project folder with clean names: <prefix>_<save name>.<ext>
    (run number added when n > 1) plus <prefix>_previews.jpg. Overwrites the previous copy."""
    try:
        os.makedirs(dest, exist_ok=True)
        pre = (prefix + "_") if prefix else ""
        for f in files:
            name = re.sub(r"^\d{2}_[^_]+_", "", f["file"])
            name = re.sub(r"_\d{5}_(?=\.[^.]+$)", "", name)
            if n > 1:
                name = re.sub(r"(\.[^.]+)$", "_%d\\1" % f["run"], name)
            shutil.copyfile(os.path.join(outdir, f["file"]), os.path.join(dest, pre + name))
        if sheet:
            shutil.copyfile(os.path.join(outdir, sheet), os.path.join(dest, pre + "previews.jpg"))
        C.log("copied %d results to %s" % (len(files), dest))
    except Exception as e:
        C.log("copy_to %s failed: %s" % (dest, e))


# ---------------------------------------------------------------- upscale any image (only when asked)
def upscale_image(path, size, model=None, name=None):
    w, h = C.parse_wh(size)
    with C.JOB_LOCK:
        C.ensure_comfy()
        up = C.upload_image(C.find_file(path))
        g = {"img": {"class_type": "LoadImage", "inputs": {"image": up}},
             "upm": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model or C.CFG.get("default_upscale_model")}},
             "up": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["upm", 0], "image": ["img", 0]}},
             "fit": {"class_type": "ImageScale", "inputs": {"image": ["up", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "center"}},
             "out": {"class_type": "PreviewImage", "inputs": {"images": ["fit", 0]}}}
        outdir = C.unique_dir(name or (os.path.splitext(os.path.basename(path))[0] + "_up"))
        info = C.wait(C.queue(g), C.CFG.get("image_timeout", 900))
        fn = os.path.splitext(os.path.basename(path))[0] + "_%dx%d.png" % (w, h)
        C.save_png(C.fetch_image(info), os.path.join(outdir, fn), {"upscaled_from": path})
        with open(os.path.join(outdir, "_done.txt"), "w", encoding="utf-8") as f:
            f.write("OK 1/1  upscale %s -> %dx%d  dir=%s\n%s\n" % (path, w, h, outdir, fn))
        C.contact_sheet(outdir, [{"id": "up", "file": fn}])
        C.set_status("done OK -> %s" % os.path.basename(outdir))
        return outdir, fn


# ---------------------------------------------------------------- conversion (ComfyUI's own frontend, hidden browser)
CONVERT_JS = r"""(async () => {
  const getApp = () => window.app || (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app);
  for (let i = 0; i < 90 && !(getApp() && getApp().graph); i++) await new Promise(r => setTimeout(r, 1000));
  const app = getApp();
  if (!app || !app.graph) return {error: 'ComfyUI frontend did not load'};
  const only = __ONLY__;
  const list = await (await fetch('/api/userdata?dir=workflows&recurse=true')).json();
  const res = {};
  for (const f of list) {
    if (!f.endsWith('.json')) continue;
    if (only && !only.some(o => f.toLowerCase().includes(String(o).toLowerCase()))) continue;
    try {
      const wf = await (await fetch('/api/userdata/' + encodeURIComponent('workflows/' + f))).json();
      const types = new Set();
      (wf.nodes || []).forEach(n => types.add(n.type));
      ((wf.definitions || {}).subgraphs || []).forEach(sg => (sg.nodes || []).forEach(n => types.add(n.type)));
      try { app.graph.clear(); } catch (e) {}
      await app.loadGraphData(wf, true, false);
      await new Promise(r => setTimeout(r, 1200));
      const p = await app.graphToPrompt();
      const foreign = [...new Set(Object.values(p.output).map(n => n.class_type).filter(t => !types.has(t)))];
      if (!Object.keys(p.output).length || foreign.length) {
        res[f] = 'ERR did not load in ComfyUI (got ' + (foreign.join(', ') || 'an empty graph') + ') - not saved';
        continue;
      }
      const name = f.replace(/\.json$/, '');
      const r = await fetch('/api/userdata/' + encodeURIComponent('comfort_api/' + name + '.api.json') + '?overwrite=true',
                            {method: 'POST', body: JSON.stringify(p.output)});
      res[f] = r.ok ? ('ok ' + Object.keys(p.output).length + ' nodes') : ('save failed ' + r.status);
    } catch (e) { res[f] = 'ERR ' + String(e).slice(0, 200); }
  }
  return res;
})()"""

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"]

def find_browser():
    for c in C.CFG.get("browser_paths", []) + BROWSERS:
        if c and os.path.exists(c):
            return c
    raise RuntimeError("no Edge/Chrome/Brave found for workflow conversion (set browser_paths in config.json)")

def convert_workflows(only=None):
    """Convert saved UI workflows to API exports. only = list of name fragments, or None for all."""
    import aiohttp
    C.ensure_comfy()
    port = int(C.CFG.get("convert_debug_port", 9333))
    profile = tempfile.mkdtemp(prefix="comfort_convert_")
    proc = subprocess.Popen([find_browser(), "--headless=new", "--remote-debugging-port=%d" % port,
                             "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check",
                             "--disable-extensions", "--window-size=1600,1000"] + ([] if os.name == "nt" else ["--no-sandbox"]) + [C.URL + "/"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    async def go():
        async with aiohttp.ClientSession() as s:
            page = None
            for _ in range(120):
                try:
                    async with s.get("http://127.0.0.1:%d/json" % port) as r:
                        targets = await r.json(content_type=None)
                    page = next((t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")
                                 and t.get("url", "").startswith(C.URL)), None)
                    if page:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            if not page:
                raise RuntimeError("hidden browser did not open ComfyUI (%s)" % C.URL)
            async with s.ws_connect(page["webSocketDebuggerUrl"], max_msg_size=0) as ws:
                for attempt in range(1, 4):
                    await ws.send_json({"id": attempt, "method": "Runtime.evaluate", "params": {
                        "expression": CONVERT_JS.replace("__ONLY__", json.dumps(only)), "awaitPromise": True, "returnByValue": True}})
                    async for msg in ws:
                        d = json.loads(msg.data)
                        if d.get("id") != attempt:
                            continue
                        if "error" in d:
                            last = str(d["error"])
                            break
                        r = d.get("result", {})
                        if "exceptionDetails" in r:
                            raise RuntimeError(str(r["exceptionDetails"])[:500])
                        return r.get("result", {}).get("value")
                    await asyncio.sleep(2)
                raise RuntimeError("conversion failed: %s" % last)
    try:
        C.set_status("converting workflows")
        res = asyncio.run(go())
        C.log("converted workflows: %s" % res)
        C.set_status("idle (converted %d workflows)" % len(res or {}))
        ensure_builtin_workflows()
        return res
    finally:
        proc.terminate()
        time.sleep(1)
        shutil.rmtree(profile, ignore_errors=True)


# ---------------------------------------------------------------- Comfort's own workflows (always available)
def ensure_builtin_workflows():
    """Write Comfort-built API workflows: a faithful rebuild of the Krea 2 RedCraft path (its original
    graph cannot be converted), the image->prompt->Krea one-pass flow, and the H3 Director under a clear name."""
    os.makedirs(api_dir(), exist_ok=True)
    g, ref = C.g_krea("describe the image here", 1, 1376, 768, {})
    C.finish(g, ref, 1376, 768, None, None)
    g["pos"]["_meta"] = {"title": "Prompt"}
    g["lat"]["_meta"] = {"title": "Size"}
    with open(wf_path("Krea 2 RedCraft (Comfort)"), "w", encoding="utf-8") as f:
        json.dump(g, f, indent=1)
    g2 = json.loads(json.dumps(g))
    k = C.CFG["i2p"]
    g2["img"] = {"class_type": "LoadImage", "inputs": {"image": "example.png"}, "_meta": {"title": "Reference image"}}
    g2["gen"] = {"class_type": "TextGenerate", "_meta": {"title": "Image to prompt"}, "inputs": {
        "clip": ["clip", 0], "prompt": k["system"], "image": ["img", 0], "max_length": int(k.get("max_length", 512)),
        "sampling_mode": "on", "sampling_mode.temperature": 0.7, "sampling_mode.top_k": 64, "sampling_mode.top_p": 0.95,
        "sampling_mode.min_p": 0.05, "sampling_mode.repetition_penalty": 1.05, "sampling_mode.seed": 1,
        "thinking": True, "use_default_template": True}}
    g2["pos"]["inputs"]["text"] = ["gen", 0]
    g2["txt"] = {"class_type": "PreviewAny", "inputs": {"source": ["gen", 0]}}
    with open(wf_path("Krea2 From Image (Comfort)"), "w", encoding="utf-8") as f:
        json.dump(g2, f, indent=1)
    src = wf_path("Working")
    if os.path.exists(src):
        with open(src, encoding="utf-8") as f:
            w = json.load(f)
        if any(n.get("class_type") == "MiniMaxH3Director" for n in w.values()):
            with open(wf_path("MiniMax H3 Director (Comfort)"), "w", encoding="utf-8") as f:
                json.dump(w, f, indent=1)

def director_id(g):
    return next(nid for nid, n in g.items() if n.get("class_type") == "MiniMaxH3Director")
