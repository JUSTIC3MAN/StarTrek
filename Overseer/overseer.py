#!/usr/bin/env python3
"""Star Trek OVERSEER - the local AI that checks every picture and shot and keeps the GPU busy (Justice 2026-10-27).
Production must never wait on Claude: Comfort runs `python overseer.py tick` between jobs and every 20 s when idle.

One tick, for every song in songs.txt (mode auto = keep producing, check = only check, off = skip):
  1. FEED   when Comfort's inbox is nearly empty, queue the song's next batch (FilmCraft song_jobs.py --queue --batch N)
            so the GPU never sits idle.
  2. ORDER  move each new <run>_stage60 job right behind its run, so finished batches can be built at once.
  3. PICS   before any video uses a picture, the local vision AI checks it (people, border/blank paper, text, style,
            brief, beauty score); a bad one is re-made (up to 2 times) and copied over the old file.
  4. SHOTS  every H3 run: motion per frame (ffmpeg, no AI) finds where each shot starts moving (its in-point), frozen
            shots and stray frames; then the vision AI looks at one contact sheet per run (sheets\\<run>.jpg). A failed
            shot gets a re-render with a new seed (up to 2); the best take of each shot goes to
            FilmCraft\\projects\\<song>\\_review.json, which song_cut.py uses (take, in-point, out-point).
  5. BUILD  every new shot goes into the song's FilmCraft project at its SongMap time as soon as it exists (rebuild;
            re-renders swap in later), and the edit is copied to Preview.
Logs: logs\\<song>.log (every decision), report_<song>.txt (one line per shot). Standards: rules.txt (edit it).
Commands: tick | status | pause | resume | build <song> | selftest <song> <run>.  PAUSE file here = do nothing.
"""
import base64, json, os, re, statistics, shutil, subprocess, sys, time, traceback, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.dirname(HERE)
COMFORT, FILM = os.path.join(ST, "Comfort"), os.path.join(ST, "FilmCraft")
INBOX, VIDEOS, VINFO = os.path.join(COMFORT, "inbox"), os.path.join(COMFORT, "out", "videos"), os.path.join(COMFORT, "out", "video_info")
SHEETS, LOGS = os.path.join(HERE, "sheets"), os.path.join(HERE, "logs")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
EXE = sys.executable[:-5] + ".exe" if sys.executable.lower().endswith("pythonw.exe") else sys.executable
MAX_RETAKES, MAX_FIXES, RUNS_PER_TICK, PICS_PER_TICK = 2, 2, 2, 8
# LEVELS (Justice 2026-11-03). Overseer\level.txt holds one word for every song; a third word in songs.txt overrides it
# for one song ("floral auto strict"). Default: light.
#   strict  exactly the Overseer as it ran before 2026-11-03 (nothing stricter): vision AI judges every picture and every
#           video, the edit is rebuilt after every shot and watched, up to 2 re-renders per run right away.
#   light   the GPU only generates: free ffmpeg motion trims (in/out points, stray frames, frozen ends) + the quick picture
#           check; no vision review of videos, no rebuild per shot. ONE build when the whole song is placed and no re-render
#           is waiting; at most 1 re-render per run, only for a hard failure, queued after every first-pass job ("zz").
#   off     the Overseer does nothing for that song (same as mode off in songs.txt).
# On request at any level: "python overseer.py build <song>" (or the interface's rebuild).
LEVELS = ("strict", "light", "off")


def level_of(song=None):
    lv = "light"
    try:
        lv = open(os.path.join(HERE, "level.txt"), encoding="utf-8").read().split()[0].lower()
    except Exception:
        pass
    if song:
        try:
            for ln in open(os.path.join(HERE, "songs.txt"), encoding="utf-8"):
                w = ln.split("#")[0].split()
                if len(w) >= 3 and w[0] == song and w[2].lower() in LEVELS:
                    lv = w[2].lower()
        except Exception:
            pass
    return lv if lv in LEVELS else "light"
FROZEN = 0.5                     # median frame-to-frame change (0-255 grey at 96x54) below this = frozen shot
STATE = {"vlm": None, "freed": False, "novision": False}


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(song, msg):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, song + ".log"), "a", encoding="utf-8") as f:
        f.write(f"{now()} {msg}\n")
    print(f"{song}: {msg}")


def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsave(p, d):
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(p + ".tmp", p)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, creationflags=NOWIN, **kw)


def put(name, text):
    tmp = os.path.join(INBOX, ".ov_" + name)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, os.path.join(INBOX, name))


def pending():
    return sorted(f for f in os.listdir(INBOX) if f.lower().endswith((".txt", ".json")) and not f.startswith(("_", ".")))


def yes(v):
    return v is True or str(v).strip().lower() in ("true", "yes", "1")


def num(v):
    try:
        return float(v)
    except Exception:
        return None


# ---------------- the local vision AI (Ollama, the same model as Comfort's local AI) ----------------
def http(url, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def ollama_up(url):
    for i in range(15):
        try:
            http(url + "/api/tags", timeout=3)
            return True
        except Exception:
            exe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
            if i == 0 and os.path.exists(exe):
                subprocess.Popen([exe, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 close_fds=True, creationflags=NOWIN | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            time.sleep(2)
    return False


def vlm(img, question):
    if STATE["novision"]:
        return None
    c = jload(os.path.join(COMFORT, "config.json"), {})
    llm, comfy = c.get("llm", {}), c.get("comfy_url", "http://127.0.0.1:8189").rstrip("/")
    url = llm.get("url", "http://127.0.0.1:11434").rstrip("/")
    if not ollama_up(url):
        STATE["novision"] = True
        return None
    if not STATE["freed"]:                   # give the GPU to the vision model (ComfyUI reloads for the next job)
        try:
            http(comfy + "/free", {"unload_models": True, "free_memory": True}, timeout=30)
        except Exception:
            pass
        STATE["freed"] = True
    STATE["vlm"] = (url, llm.get("model", "qwen3.6:27b"))
    with open(os.path.join(HERE, "rules.txt"), encoding="utf-8") as f:
        rules = f.read()
    with open(img, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = {"model": STATE["vlm"][1], "stream": False, "format": "json", "think": False, "keep_alive": "5m",
            "options": {"temperature": 0.1, "num_ctx": 8192},
            "messages": [{"role": "system", "content": rules}, {"role": "user", "content": question, "images": [b64]}]}
    err = None
    for _ in range(2):
        try:
            txt = http(url + "/api/chat", body, timeout=900).get("message", {}).get("content", "")
            return json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
        except Exception as e:
            err = e
            body.pop("think", None)
    print("vision check failed:", err)
    return None


def vlm_unload():
    if STATE["vlm"]:
        try:
            http(STATE["vlm"][0] + "/api/generate", {"model": STATE["vlm"][1], "keep_alive": 0}, timeout=30)
        except Exception:
            pass


def check_picture(p, desc, look, people=None):
    os.makedirs(SHEETS, exist_ok=True)
    jp = os.path.join(SHEETS, "pic_" + os.path.splitext(os.path.basename(os.path.dirname(p)) + "_" + os.path.basename(p))[0] + ".jpg")
    sh(["ffmpeg", "-v", "error", "-y", "-i", p, "-vf", "scale=1024:-2", jp])
    q = ("This picture is a still for a music video. It was asked to show: " + desc + "\nThe look must be: " + look +
         '\nAnswer only JSON: {"people": true/false, "border": true/false, "text": true/false, "style_ok": true/false, '
         '"matches": true/false, "score": 1-10, "note": "short reason"}. people = any person, face, hand or body, except '
         + (people or 'one tiny far-off silhouette of a woman') + '; border = any border, margin, frame, blank or plain paper, or art not filling '
         'the frame edge to edge; text = any letters, numbers or watermark; matches = it shows what was asked.')
    a = vlm(jp if os.path.exists(jp) else p, q)
    if not a:
        return True, "not checked (vision AI unavailable)", None
    probs = [k for k in ("people", "border", "text") if yes(a.get(k))]
    probs += [k for k, v in (("off-style", a.get("style_ok")), ("off-brief", a.get("matches"))) if v is not None and not yes(v)]
    sc = num(a.get("score"))
    if sc is not None and sc < 5:
        probs.append(f"score {sc:g}")
    return not probs, ", ".join(probs + ([str(a["note"])[:160]] if a.get("note") else [])), sc


# ---------------- motion (no AI): in-point, frozen shots, stray frames ----------------
def decode(vp):
    m = re.search(r"([\d.]+) fps", sh(["ffmpeg", "-hide_banner", "-i", vp], text=True).stderr or "")
    fps = float(m.group(1)) if m else 24.0
    raw = sh(["ffmpeg", "-v", "error", "-i", vp, "-vf", "scale=96:54,format=gray", "-f", "rawvideo", "-"]).stdout
    n = 96 * 54
    return fps, [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]


def analyse_slot(d, fps, sl, seg=5.0):
    i0, i1 = int(round(seg * sl * fps)), min(len(d), int(round((seg * sl + seg) * fps)))
    idx = list(range(i0 + 1, i1))
    if len(idx) < fps:
        return {"in": 0.4, "out": 4.98, "motion": 0, "ok": False, "hard": True, "why": "shot missing"}
    rel = lambda i: i / fps - seg * sl
    sm = {i: statistics.mean(d[max(i0 + 1, i - 2):min(i1, i + 3)]) for i in idx}
    tail = [d[i] for i in idx if seg / 2 <= rel(i) <= seg - 0.1]
    level = statistics.median(tail) if tail else 0.0
    med = statistics.median([d[i] for i in idx])
    inp = next((rel(i) for i in idx if rel(i) >= 0.3 and level > 0 and sm[i] >= 0.5 * level), 2.8)
    inp, out, why, hard = max(0.4, min(2.8, inp)), round(seg - 0.02, 2), [], False
    for i in idx[2:-2]:
        t = rel(i)
        if t < 0.2 or t > seg - 0.15 or t < inp:
            continue
        around = d[max(i0 + 1, i - 6):i - 1] + d[i + 3:min(i1, i + 8)]
        base = statistics.median(around) if around else med
        if d[i] < max(10.0, 4 * base, 2.5 * med):
            continue
        if t + 0.1 <= 2.5:
            inp = t + 0.1
            why.append(f"stray frame at {t:.1f}s skipped")
        elif t >= inp + 2.2:
            out = t - 0.05
            why.append(f"stray frame at {t:.1f}s trimmed")
            break
        else:
            why.append(f"stray frame/cut at {t:.1f}s")
            hard = True
            break
    live = sorted(sm[i] for i in idx if inp <= rel(i) <= seg - 0.1)
    peak = live[int(len(live) * 0.8)] if live else 0.0
    last = max((rel(i) for i in idx if inp <= rel(i) <= seg - 0.1 and sm[i] >= max(FROZEN, 0.35 * peak)), default=inp)
    if peak >= FROZEN and last + 0.1 < out:                # it stops moving before the end: cut the static end (slowed to fit)
        out = round(last + 0.1, 2)
        why.append(f"static end cut at {out:.1f}s")
    if peak < FROZEN or out - inp < 1.2:
        why.append(f"frozen (motion {peak:.2f})")
        hard = True
    elif inp >= 2.8:
        why.append("starts moving late")
    return {"in": round(inp, 2), "out": round(out, 2), "motion": round(level, 2), "ok": not hard, "hard": hard, "why": "; ".join(why)}


def check_run(look, take, jf, nslot=3, people=None):
    vp = os.path.join(VIDEOS, take + ".mp4")
    fps, fr = decode(vp)
    d = [0.0] + [sum(abs(x - y) for x, y in zip(a, b)) / len(a) for a, b in zip(fr, fr[1:])]
    seg = len(fr) / fps if nslot == 1 else 5.0
    slots = [analyse_slot(d, fps, sl, seg) for sl in range(nslot)]
    if STATE.get("level", "light") != "strict":      # light: motion trims only, no contact sheet, no vision AI
        return {"slots": slots, "fps": fps, "checked": now(), "vision": "light: motion check only"}
    descs = dict(re.findall(r"<Picture (\d)> is the first frame of \[Shot \d\], showing (.+)", jload(jf, {}).get("set", {}).get("ref.prompt", "")))
    os.makedirs(SHEETS, exist_ok=True)
    sheet, ns = os.path.join(SHEETS, take + ".jpg"), []
    for sl, s in enumerate(slots):
        for k in range(5):
            n = int(round((seg * sl + s["in"] + (s["out"] - 0.1 - s["in"]) * k / 4) * fps))
            ns.append(min(len(fr) - 1, max(n, ns[-1] + 1 if ns else 0)))
    sel = "+".join(f"eq(n\\,{n})" for n in ns)
    sh(["ffmpeg", "-v", "error", "-y", "-i", vp, "-vf", f"select='{sel}',scale=320:180,tile=5x{nslot}", "-frames:v", "1", sheet])
    res = {"slots": slots, "fps": fps, "checked": now()}
    if not os.path.exists(sheet):
        return res
    rows = "\n".join(f"Row {i + 1} should show: {descs.get(str(i + 1), '(see the picture)')}" for i in range(nslot))
    q = (f"This contact sheet has {nslot} row(s). Each row is one shot of a music video: 5 frames from left to right in time order.\n{rows}\n"
         f"The look must be: {look}\nFor each row answer: people (true if any person, face, hand or body appears, except "
         + (people or "one tiny far-off silhouette of a woman") + "), glitch (true if a frame is broken, a different picture suddenly appears, shapes melt or "
         "smear, or text or a border appears), style_ok (true if every frame keeps the look), moving (true if the frames clearly "
         "change from left to right), score (1-10: how beautiful and cinematic it is for a concert screen), note (short).\n"
         'Answer only JSON: {"rows": [{"row": 1, "people": false, "glitch": false, "style_ok": true, "moving": true, "score": 7, "note": "..."}, {"row": 2}, {"row": 3}]}')
    a = vlm(sheet, q)
    if not a:
        res["vision"] = "unavailable: motion check only"
        return res
    got = a.get("rows") or []
    for i, s in enumerate(slots):
        r = next((x for x in got if isinstance(x, dict) and str(x.get("row")) == str(i + 1)), got[i] if i < len(got) else None)
        if not isinstance(r, dict):
            continue
        sc = num(r.get("score"))
        s["score"], s["note"] = sc, str(r.get("note", ""))[:160]
        probs = [k for k in ("people", "glitch") if yes(r.get(k))]
        asked = people or re.search(r"silhouette|woman|figure", descs.get(str(i + 1), ""), re.I)   # #people in shots.txt: the song's own allowed people   # the far-off woman was asked for: a size call, not a hard fail
        if r.get("style_ok") is not None and not yes(r.get("style_ok")):
            probs.append("off-style")
        if sc is not None and sc < 5:
            probs.append(f"score {sc:g}")
        if probs:
            s["ok"], s["hard"] = False, s["hard"] or ("people" in probs and not asked) or "glitch" in probs
            s["why"] = "; ".join(x for x in (s["why"], ", ".join(probs), s["note"]) if x)
    return res


# ---------------- one song ----------------
class Song:
    def __init__(self, name, mode):
        self.name, self.mode = name, mode
        self.pdir = os.path.join(FILM, "projects", name)
        self.jdir = os.path.join(self.pdir, "_jobs")
        self.cfg, self.look, self.looks = {"pics": name, "prefix": "z", "queue": "a"}, "", {}
        with open(os.path.join(self.pdir, name + ".shots.txt"), encoding="utf-8") as f:
            for ln in f:
                m = re.match(r"#(\w+)\s+(.*)", ln.strip())
                if m:
                    self.cfg[m.group(1)] = m.group(2).strip()
                elif ln.startswith("style "):              # every style's look (2026-11-03: songs like FLORAL change style by section)
                    sf = [x.strip() for x in ln[6:].split("|")]
                    self.looks[sf[0]] = sf[-1]
                    if not self.look:
                        self.look = sf[-1]
        self.label_look = {}                           # shot label -> the look of its own style key
        with open(os.path.join(self.pdir, name + ".shots.txt"), encoding="utf-8") as f:
            for ln in f:
                sf = [x.strip() for x in ln.split("|")]
                if len(sf) >= 4 and not ln.startswith("#"):
                    key = re.split(r"[@>]", sf[1])[0].strip()
                    if key in self.looks:
                        self.label_look[sf[3]] = self.looks[key]
        self.pre, self.q = self.cfg["prefix"], self.cfg["queue"]
        self.rfile = os.path.join(self.pdir, "_review.json")
        self.rv = jload(self.rfile, {})
        for k in ("runs", "pics", "retakes", "use", "fixes", "final"):
            self.rv.setdefault(k, {})
        self.rv.setdefault("built", 0)
        self.rv.setdefault("locked", {})
        rx = re.compile(re.escape(self.pre) + r"(\d\d)" + re.escape(self.q) + r"(\d[a-z]?)_(.+)\.(json|txt)$")
        self.jobs = []                                   # (batch, kind 0p/0q/0x/1, stem, file)
        for f in sorted(os.listdir(self.jdir)) if os.path.isdir(self.jdir) else []:
            m = rx.match(f)
            if m:
                self.jobs.append((int(m.group(1)), m.group(2), m.group(3), f))
        qf = os.path.join(self.jdir, "queued.txt")
        self.queued = {l.split()[0] for l in open(qf, encoding="utf-8") if l.strip()} if os.path.exists(qf) else set()
        self.plan = jload(os.path.join(self.pdir, name + ".plan.json"), {"shots": []})

    def save(self):
        self.rv["use"].update(self.rv.get("locked", {}))     # Justice's decisions always win
        jsave(self.rfile, self.rv)

    def look_of(self, label):
        """The look a picture is judged against: its own shot's style (first style if unknown)."""
        return self.label_look.get(label, self.look)

    def run_look(self, jf):
        """The look an H3 run is judged against, read from its own prompt: one look, or one per row when its shots differ."""
        try:
            pr = jload(jf, {}).get("set", {}).get("ref.prompt", "")
            m = re.search(r"<Subject 1> is the rendering style of <Picture 1>, <Picture 2> and <Picture 3>: (.+?)\.\n", pr)
            if m:
                return m.group(1)
            m = re.search(r"every shot keeps the look of its own first frame \((.+?)\)\.\n", pr)
            if m:
                return ("each row keeps its own look (the song changes style by section) - "
                        + re.sub(r"<Picture (\d)>", r"row \1", m.group(1)))
        except Exception:
            pass
        return self.look

    def label(self, run, sl):
        return next((s["label"] for s in self.plan.get("shots", []) if s.get("run") == run and s.get("slot") == sl), f"{run}:{sl}")

    def feed(self):
        if self.mode != "auto" or len(pending()) > 1:
            return False
        todo = sorted({b for b, k, s, f in self.jobs if f not in self.queued})
        if not todo:
            return False
        r = sh([EXE, os.path.join(FILM, "song_jobs.py"), self.name, "--queue", "--batch", str(todo[0])], cwd=FILM, text=True, timeout=180)
        out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        log(self.name, f"queued batch {todo[0]} (inbox was nearly empty): {out[0][:220] if out else r.returncode}")
        return True

    def move_stage(self):
        pref = {s: f"{self.pre}00{self.q}_" for b, k, s, f in self.jobs if k == "1"}
        for f in pending():
            m = re.match(r"(.+?)(_t\d+)?_stage60\.json$", f)
            if m and (m.group(1) in pref or m.group(1).startswith(self.cfg["pics"] + "_shot_")):
                os.replace(os.path.join(INBOX, f), os.path.join(INBOX, pref.get(m.group(1), f"{self.pre}00{self.q}_") + f))

    def review_pics(self, budget):
        for fx, d in list(self.rv["fixes"].items()):         # finished re-makes go over the old picture
            od = os.path.join(COMFORT, "out", fx)
            if not os.path.exists(os.path.join(od, "_done.txt")):
                continue
            new = [x for x in os.listdir(od) if x.endswith(".png") and not x.startswith("_")]
            if new and open(os.path.join(od, "_done.txt"), encoding="utf-8").read().startswith("OK"):
                dest = d["dest"]
                if os.path.exists(dest):
                    os.replace(dest, os.path.join(os.path.dirname(dest), f"_rejected_{fx}_{os.path.basename(dest)}"))
                shutil.copyfile(os.path.join(od, new[0]), dest)
                log(self.name, f"picture {os.path.basename(dest)} replaced by its re-make {fx}")
            else:
                log(self.name, f"re-make {fx} failed; keeping the old picture")
            del self.rv["fixes"][fx]
        pend, done = pending(), 0
        fixing = {d["dest"] for d in self.rv["fixes"].values()}
        for b, k, stem, f in self.jobs:
            if not k.startswith("0") or f not in self.queued:
                continue
            runs_b = [st for bb, kk, st, ff in self.jobs if bb == b and kk == "1"]
            if not any(p.endswith("_" + r + ".json") for p in pend for r in runs_b):
                continue                                     # its videos are made already: too late to matter
            od = os.path.join(COMFORT, "out", stem)
            if not os.path.exists(os.path.join(od, "_done.txt")):
                continue
            lines = open(os.path.join(self.jdir, f), encoding="utf-8").read().splitlines()
            head = [l for l in lines if l.startswith("#") and not l.startswith("#name")]
            for l in lines:
                m = re.match(r"\[label=(\S+)[^\]]*\]\s*(.*)", l)
                hit = m and [x for x in os.listdir(od) if x.endswith("_" + m.group(1) + ".png") and not x.startswith("_")]
                if not hit:
                    continue
                p = os.path.join(od, hit[0])
                key, mt = os.path.relpath(p, COMFORT), os.path.getmtime(p)
                st = self.rv["pics"].get(key, {})
                if st.get("m") == mt or p in fixing:
                    continue
                if done >= budget:
                    return
                done += 1
                ok, why, sc = check_picture(p, m.group(2), self.look_of(m.group(1)), self.cfg.get("people"))
                st.update(m=mt, ok=ok, why=why, score=sc)
                self.rv["pics"][key] = st
                if ok:
                    log(self.name, f"picture {m.group(1)} ok (score {sc}) {why}")
                elif st.get("fixes", 0) < MAX_FIXES:
                    n = st.get("fixes", 0) + 1
                    st["fixes"], fx = n, f"{stem}_{m.group(1)}_f{n}"
                    put(f"{self.pre}{b:02d}{self.q}0{'y' if k == '0x' else 'r'}_{fx}.txt", "\n".join(head + [f"#name {fx}", l]) + "\n")
                    self.rv["fixes"][fx] = {"dest": p}
                    log(self.name, f"picture {m.group(1)} REJECTED ({why}): re-make {n} queued")
                else:
                    log(self.name, f"picture {m.group(1)} still weak after {MAX_FIXES} re-makes ({why}): kept")
                self.save()

    def review_runs(self, budget):
        done = 0
        for b, k, stem, f in self.jobs:
            if k != "1" or f not in self.queued:
                continue
            takes = [stem] + [f"{stem}_t{i}" for i in range(1, self.rv["retakes"].get(stem, 0) + 1)]
            for t in takes:
                dn = os.path.join(VINFO, t, "_done.txt")
                if t in self.rv["runs"] or not os.path.exists(dn) or done >= budget:
                    continue
                done += 1
                if not open(dn, encoding="utf-8").read().startswith("OK") or not os.path.exists(os.path.join(VIDEOS, t + ".mp4")):
                    bad = {"in": 0.4, "out": 4.98, "motion": 0, "ok": False, "hard": True, "why": "render failed"}
                    self.rv["runs"][t] = {"slots": [dict(bad) for _ in range(3)], "checked": now()}
                else:
                    self.rv["runs"][t] = check_run(self.run_look(os.path.join(self.jdir, f)), t, os.path.join(self.jdir, f), people=self.cfg.get("people"))
                r = self.rv["runs"][t]["slots"]
                log(self.name, f"checked {t}: " + " | ".join(
                    f"{self.label(stem, i)} {'ok' if s['ok'] else 'REJECT'} in {s['in']} out {s['out']} motion {s['motion']}"
                    + (f" score {s.get('score')}" if s.get("score") is not None else "") + (f" ({s['why']})" if s["why"] else "") for i, s in enumerate(r)))
                self.save()
            self.decide(stem, f)

    def extras(self):
        """Re-generated single shots (<pics>_shot_<label>_<tag>: 3 different takes of one picture): check them, put every
        take in Preview as '<label> new take N.mp4', and lock the best one into its spot in the edit."""
        pre = self.cfg["pics"] + "_shot_"
        ex = self.rv.setdefault("extras", {})
        for d in sorted(os.listdir(VINFO)) if os.path.isdir(VINFO) else []:
            stage = os.path.join(VIDEOS, d + "_stage60.mp4")
            if not d.startswith(pre) or d.endswith("_stage60") or d in ex or not os.path.exists(stage):
                continue
            label = d[len(pre):].split("_")[0]
            jf = os.path.join(self.jdir, "x_" + d + ".json")
            one = int(jload(jf, {}).get("set", {}).get("ref.length", 362)) < 300     # one long shot, not three
            res = check_run(self.run_look(jf), d, jf, 1 if one else 3, people=self.cfg.get("people"))
            seg = 0.0 if one else 5.0
            self.rv["runs"][d] = res
            pv = os.path.dirname(self.cfg.get("copy", "").split("|")[0].strip()) or HERE
            for k, s in enumerate(res["slots"]):
                sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{seg * k + s['in']:.2f}", "-i", stage, "-t", f"{s['out'] - s['in']:.2f}", "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", os.path.join(pv, f"{label} new.mp4" if one else f"{label} new take {k + 1}.mp4")])
            good = [((s.get("score") or 0), k, s) for k, s in enumerate(res["slots"]) if s["ok"]] or \
                   [((s.get("score") or 0), k, s) for k, s in enumerate(res["slots"]) if not s.get("hard")]
            shot = next((x for x in self.plan.get("shots", []) if x["label"].startswith(label) and "run" in x), None)
            if good and shot:
                sc, k, s = max(good, key=lambda g: (g[0], -g[1]))
                self.rv["locked"][f"{shot['run']}:{shot['slot']}"] = {"run": d, "slot": k, "in": 0.0 if one else s["in"], "out": s["out"], "one": one, "why": f"new take {k + 1}, score {sc:g}"}
                self.rv["build_sig"] = None
                log(self.name, f"{shot['label']}: new generation in Preview ('{label} new.mp4'), now the opening of the edit (score {sc:g}, used {s['in']}-{s['out']} s, slowed to fit)" if one
                    else f"{shot['label']}: 3 new takes in Preview ('{label} new take 1-3.mp4'); take {k + 1} (score {sc:g}) is now in the edit")
            else:
                log(self.name, f"{label}: new takes in Preview, but none passed: " + " | ".join(s["why"] for s in res["slots"]))
            ex[d] = now()
            self.save()

    def neighbour(self, stem, sl):
        """NO REPEATS (Justice 2026-10-27, README rule 3): another shot never stands in for this one - that showed the
        meteor twice. song_cut holds the shot before it (slowed) until this one passes."""
        return None
        shots = [s for s in self.plan.get("shots", []) if "run" in s]
        i = next((k for k, s in enumerate(shots) if s["run"] == stem and s["slot"] == sl), None)
        if i is None:
            return None
        sec, k = [], 0
        for s in shots:
            k += 1 if s.get("tr") else 0
            sec.append(k)
        for j in sorted(range(len(shots)), key=lambda j: (sec[j] != sec[i], abs(j - i) < 2, abs(j - i))):
            u = self.rv["use"].get(f"{shots[j]['run']}:{shots[j]['slot']}")
            if j != i and u and not u.get("why"):
                v = dict(u, why=f"covered by {shots[j]['label']}")
                v["in"] = round(min(v["out"] - 1.6, v["in"] + 0.8), 2)
                return v
        return None

    def decide(self, stem, f):
        n = self.rv["retakes"].get(stem, 0)
        takes = [stem] + [f"{stem}_t{i}" for i in range(1, n + 1)]
        revs = [self.rv["runs"].get(t) for t in takes]
        if self.rv["final"].get(stem):
            return
        if any(r is None for r in revs):             # a re-render is still coming: a good shot of the scene holds each rejected spot
            for sl in range(3):
                key = f"{stem}:{sl}"
                if key not in self.rv["use"] and all(r is None or not r["slots"][sl]["ok"] for r in revs):
                    soft = [(r["slots"][sl], t) for t, r in zip(takes, revs) if r and not r["slots"][sl].get("hard")]
                    if soft:                         # a usable take holds the spot (no shot is ever shown twice in a row)
                        s, t = max(soft, key=lambda c: c[0].get("score") or 0)
                        self.rv["use"][key] = {"run": t, "slot": sl, "in": s["in"], "out": s["out"], "why": "holding: best take so far"}
                    else:
                        u = self.neighbour(stem, sl)
                        if u:
                            self.rv["use"][key] = dict(u, why="holding until the re-render passes")
            return
        used = {(s.get("run"), s.get("slot")) for s in self.plan.get("shots", [])}
        bad = []
        for sl in range(3):
            okt = next((t for t, r in zip(takes, revs) if r["slots"][sl]["ok"]), None)
            if okt:
                s = self.rv["runs"][okt]["slots"][sl]
                self.rv["use"][f"{stem}:{sl}"] = {"run": okt, "slot": sl, "in": s["in"], "out": s["out"]}
            elif (stem, sl) in used:
                bad.append(sl)
        lv = STATE.get("level", "light")
        if bad and n < {"strict": MAX_RETAKES, "light": 1}.get(lv, 0):
            body = jload(os.path.join(self.jdir, f), None)
            if body:
                body["name"], body["seed"] = f"{stem}_t{n + 1}", "random"
                put(("zz" if lv != "strict" else "") + f"{f[:-5]}_t{n + 1}.json", json.dumps(body))   # light: after every first-pass job
                self.rv["retakes"][stem] = n + 1
                for sl in bad:                       # never place a rejected shot: a good one of the same scene holds the spot
                    u = self.neighbour(stem, sl)
                    if u:
                        self.rv["use"][f"{stem}:{sl}"] = dict(u, why="holding until the re-render passes")
                    else:
                        self.rv["use"].pop(f"{stem}:{sl}", None)
                log(self.name, f"{stem}: re-render {n + 1} queued for " + ", ".join(self.label(stem, sl) for sl in bad))
                self.save()
                return
        for sl in bad:
            cands = [(r["slots"][sl], t) for t, r in zip(takes, revs) if not r["slots"][sl].get("hard")]
            if cands:
                s, t = max(cands, key=lambda c: c[0].get("score") or 0)
                self.rv["use"][f"{stem}:{sl}"] = {"run": t, "slot": sl, "in": s["in"], "out": s["out"], "why": "best of failed takes"}
                log(self.name, f"{self.label(stem, sl)}: no take passed; using the best ({t}: {s['why']})")
            else:
                u = self.neighbour(stem, sl)
                if u:
                    self.rv["use"][f"{stem}:{sl}"] = u
                log(self.name, f"{self.label(stem, sl)}: every take failed hard; " + (u["why"] if u else "left as rendered"))
        self.rv["final"][stem] = True
        self.save()

    def maybe_build(self):
        """Every generation goes into the song's FilmCraft project at its SongMap time AS SOON AS IT EXISTS (Justice's rule):
        rebuild whenever another shot can be placed or a verdict changes (a re-render swaps in later)."""
        run = os.path.join(LOGS, f"build_{self.name}.running")
        if os.path.exists(run) and time.time() - os.path.getmtime(run) < 3600:
            return
        n = 0
        for s in self.plan.get("shots", []):
            if "run" in s:
                u = self.rv["use"].get(f"{s['run']}:{s['slot']}")
                if not u or not os.path.exists(os.path.join(VIDEOS, u["run"] + "_stage60.mp4")):
                    break                            # not judged yet (or rejected with no cover): never place it
            n += 1
        sig = f"{n}|" + json.dumps(self.rv["use"], sort_keys=True)
        if not n or sig == self.rv.get("build_sig"):
            return
        if STATE.get("level", "light") != "strict":  # light/off: one build, the whole song placed and no re-render waiting
            waiting = any(x.startswith("zz") and self.cfg["pics"] in x for x in pending())
            if n < len(self.plan.get("shots", [])) or waiting:
                return
        self.rv["build_sig"], self.rv["built_shots"] = sig, n
        self.save()
        os.makedirs(LOGS, exist_ok=True)
        subprocess.Popen([EXE, os.path.abspath(__file__), "build", self.name], cwd=HERE, stdin=subprocess.DEVNULL,
                         stdout=open(os.path.join(LOGS, f"build_{self.name}.txt"), "w", encoding="utf-8"), stderr=subprocess.STDOUT,
                         close_fds=True, creationflags=NOWIN | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        log(self.name, f"{n} of {len(self.plan.get('shots', []))} shots placed: FilmCraft project rebuilding")

    def merge_edit_flags(self):
        """Stills the edit check found in the finished edit: that take is rejected, so the shot is re-rendered or covered."""
        ef = jload(os.path.join(self.pdir, "_edit_flags.json"), {})
        if not ef or ef.get("t") == self.rv.get("edit_flags_seen"):
            return
        self.rv["edit_flags_seen"] = ef.get("t")
        nb = ef.get("built") or self.rv.get("built_shots") or 0      # 2026-11-03: a partial edit has black after its last shot
        inside = {f"{x['run']}:{x['slot']}" for x in self.plan.get("shots", [])[:nb] if "run" in x}
        for fl in ef.get("flags", []):
            if nb and fl["key"] not in inside:
                continue                             # past the end of the partial edit: nothing on screen to judge
            u = self.rv["use"].get(fl["key"])
            if fl["key"] in self.rv["locked"] or not u or u["run"] not in self.rv["runs"]:
                continue
            s = self.rv["runs"][u["run"]]["slots"][u["slot"]]
            s.update(ok=False, hard=True, why=(s.get("why", "") + "; still in the finished edit").strip("; "))
            self.rv["final"].pop(fl["key"].split(":")[0], None)
            self.rv["use"].pop(fl["key"], None)
            log(self.name, f"{fl['label']} stands still in the edit at {fl['t']:.1f}s: rejected, fixing it")
        self.save()

    def report(self):
        allb = sorted({b for b, k, s, f in self.jobs})
        qb = [b for b in allb if all(f in self.queued for bb, k, s, f in self.jobs if bb == b)]
        cp = self.cfg.get("copy", "")
        L = [f"{self.cfg.get('title', self.name)} - overseer report {now()} (mode {self.mode})",
             f"batches queued {qb} of {allb} | in the FilmCraft project: {self.rv.get('built_shots', 0)} of {len(self.plan.get('shots', []))} shots",
             f"preview: {cp}", "shot                 time   run:slot           verdict"]
        for s in self.plan.get("shots", []):
            if "run" not in s:
                continue
            u = self.rv["use"].get(f"{s['run']}:{s['slot']}")
            src = u or {"run": s["run"], "slot": s["slot"]}
            r = (self.rv["runs"].get(src["run"]) or {}).get("slots")
            v = "waiting" if not r else ("ok" if r[src["slot"]]["ok"] else "weak: " + r[src["slot"]]["why"])
            if u and (u["run"] != s["run"] or u.get("why")):
                v += f"  [using {u['run']}:{u['slot']}{' - ' + u['why'] if u.get('why') else ''}]"
            L.append(f"{s['label']:<20} {s['t']:6.1f}  {s['run'] + ':' + str(s['slot']):<18} {v}")
        with open(os.path.join(HERE, f"report_{self.name}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")


def songs():
    out = []
    for ln in open(os.path.join(HERE, "songs.txt"), encoding="utf-8"):
        p = ln.split("#")[0].split()
        if p:
            out.append((p[0], p[1] if len(p) > 1 else "auto"))
    return out


def tick():
    if os.path.exists(os.path.join(HERE, "PAUSE")):
        return
    lock = os.path.join(HERE, "tick.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 1800:
        return
    open(lock, "w").close()
    try:
        try:                                     # new songs: MP3 -> SongMap -> style round -> pick -> shot list -> queue (planner.py)
            import planner
            planner.tick()
        except Exception:
            log("planner", "planner error: " + traceback.format_exc()[-700:].replace("\n", " | "))
        for name, mode in songs():
            if mode == "off" or level_of(name) == "off":
                continue
            if not os.path.isdir(os.path.join(FILM, "projects", name)):     # its project isn't on this PC (yet)
                continue
            try:
                STATE["level"] = level_of(name)
                s = Song(name, mode)
                s.move_stage()
                if s.feed():
                    s = Song(name, mode)
                s.merge_edit_flags()
                s.review_pics(PICS_PER_TICK)
                s.review_runs(RUNS_PER_TICK)
                s.extras()
                s.maybe_build()
                s.save()
                s.report()
            except Exception:
                log(name, "overseer error: " + traceback.format_exc()[-700:].replace("\n", " | "))
    finally:
        vlm_unload()
        os.remove(lock)


def edit_check(song):
    """Watch the finished edit like a viewer: any shot that stands still on screen is flagged (the tick then fixes it)."""
    pdir = os.path.join(FILM, "projects", song)
    plan = jload(os.path.join(pdir, song + ".plan.json"), {"shots": []})
    vp = os.path.join(FILM, plan.get("out", f"projects/{song}/{song}.mp4").replace("/", os.sep))
    raw = sh(["ffmpeg", "-v", "error", "-i", vp, "-vf", "fps=12,scale=96:54,format=gray", "-f", "rawvideo", "-"]).stdout
    n = 96 * 54
    fr = [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]
    d = [0.0] + [sum(abs(x - y) for x, y in zip(a, b)) / n for a, b in zip(fr, fr[1:])]
    flags = []
    nb = jload(os.path.join(pdir, "_review.json"), {}).get("built_shots") or len(plan.get("shots", []))
    for s in plan.get("shots", [])[:nb]:                 # only shots that are in this (possibly partial) edit
        ds = [d[i] for i in range(int((s["t"] + 0.2) * 12), min(len(d), int((s["e"] - 0.2) * 12)))]
        if not ds:
            break
        m = statistics.median(ds)
        if "run" in s and m < FROZEN:
            flags.append({"key": f"{s['run']}:{s['slot']}", "label": s["label"], "t": s["t"], "motion": round(m, 2)})
    jsave(os.path.join(pdir, "_edit_flags.json"), {"t": now(), "flags": flags, "built": nb})
    log(song, "watched the finished edit: " + ("every shot moves" if not flags else "standing still: " + ", ".join(f"{f['label']} at {f['t']:.1f}s" for f in flags)))


def build(song):
    run = os.path.join(LOGS, f"build_{song}.running")
    open(run, "w").close()
    try:
        r = sh([EXE, os.path.join(FILM, "fc.py"), "build", f"projects/{song}/{song}.txt"], cwd=FILM, text=True)
        out = (r.stdout or "").strip().splitlines()
        log(song, "build: " + (out[-1] if out else "FAILED " + (r.stderr or "")[-400:].replace("\n", " | ")))
        if out and out[-1].startswith("ok") and level_of(song) == "strict":
            edit_check(song)
    finally:
        os.remove(run)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tick"
    if cmd == "tick":
        tick()
    elif cmd == "build":
        build(sys.argv[2])
    elif cmd == "pause":
        open(os.path.join(HERE, "PAUSE"), "w").close()
        print("overseer paused")
    elif cmd == "resume":
        if os.path.exists(os.path.join(HERE, "PAUSE")):
            os.remove(os.path.join(HERE, "PAUSE"))
        print("overseer running")
    elif cmd == "status":
        for name, mode in songs():
            p = os.path.join(HERE, f"report_{name}.txt")
            print(open(p, encoding="utf-8").read() if os.path.exists(p) else f"{name}: no report yet")
    elif cmd in ("new", "pick", "planstatus", "restyle", "replan"):
        import planner
        planner.cli(sys.argv[1:])
    elif cmd == "mode":
        rows, hit = [], False
        for ln in open(os.path.join(HERE, "songs.txt"), encoding="utf-8"):
            p = ln.split()
            if p and p[0] == sys.argv[2]:
                ln, hit = f"{sys.argv[2]} {sys.argv[3]}\n", True
            rows.append(ln)
        rows += [] if hit else [f"{sys.argv[2]} {sys.argv[3]}\n"]
        open(os.path.join(HERE, "songs.txt"), "w", encoding="utf-8").write("".join(rows))
        print(f"{sys.argv[2]}: mode {sys.argv[3]}")
    elif cmd == "shots" and len(sys.argv) > 3:            # only the lines that match (a label, a section name)
        p = os.path.join(FILM, "projects", sys.argv[2], sys.argv[2] + ".shots.txt")
        print("\n".join(l for l in open(p, encoding="utf-8").read().splitlines() if sys.argv[3].lower() in l.lower())[:4000] or "no match")
    elif cmd in ("shots", "songmap"):
        pdir = os.path.join(FILM, "projects", sys.argv[2])
        f = os.path.join(pdir, sys.argv[2] + ".shots.txt") if cmd == "shots" else next(
            (os.path.join(pdir, x) for x in os.listdir(pdir) if x.endswith(".songmap.txt")), None)
        print(open(f, encoding="utf-8").read() if f and os.path.exists(f) else "not found")
    elif cmd == "setshots":
        p = os.path.join(FILM, "projects", sys.argv[2], sys.argv[2] + ".shots.txt")
        bak = p + time.strftime(".%Y%m%d-%H%M%S.bak")
        if os.path.exists(p):
            shutil.copyfile(p, bak)
        shutil.copyfile(sys.argv[3], p)
        r = sh([EXE, os.path.join(FILM, "song_jobs.py"), sys.argv[2]], cwd=FILM, text=True, timeout=180)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if r.returncode and os.path.exists(bak):
            shutil.copyfile(bak, p)
            out += "\nINVALID shot list: the old one is restored."
        print(out)
    elif cmd in ("rules", "readme"):
        print(open(os.path.join(HERE, "rules.txt") if cmd == "rules" else os.path.join(ST, "README.txt"), encoding="utf-8").read())
    elif cmd == "redo":                                    # redo <song> <shot label>: Justice (or the local AI) wants it re-rendered
        s = Song(sys.argv[2], "auto")
        shot = next((x for x in s.plan.get("shots", []) if x["label"].startswith(sys.argv[3]) and "run" in x), None)
        f = shot and next((f for b, k, st, f in s.jobs if st == shot["run"] and k == "1"), None)
        if not f:
            print("no such shot: " + sys.argv[3])
        else:
            stem, n = shot["run"], s.rv["retakes"].get(shot["run"], 0) + 1
            u = s.rv["use"].get(f"{stem}:{shot['slot']}")
            if u and u["run"] in s.rv["runs"]:
                s.rv["runs"][u["run"]]["slots"][u["slot"]].update(ok=False, why="Justice asked for a redo")
            body = jload(os.path.join(s.jdir, f), {})
            body["name"], body["seed"] = f"{stem}_t{n}", "random"
            put(f"{f[:-5]}_t{n}.json", json.dumps(body))
            s.rv["retakes"][stem] = n
            s.rv["final"].pop(stem, None)
            s.save()
            log(s.name, f"{shot['label']}: redo requested, re-render {n} queued")
    elif cmd == "trim":                                    # trim <song> <label> <percent>: cut the end of a shot, the rest is slowed to fit
        s = Song(sys.argv[2], "auto")
        pct = float(sys.argv[4]) if len(sys.argv) > 4 else 15
        hit = [x for x in s.plan.get("shots", []) if x["label"].startswith(sys.argv[3]) and "run" in x]
        for x in hit:
            u = s.rv["use"].get(f"{x['run']}:{x['slot']}")
            if u:
                u["out"] = round(u["in"] + (min(u["out"], float(s.plan.get("tail", 4.98))) - u["in"]) * (1 - pct / 100), 2)
        s.rv["build_sig"] = None
        s.save()
        log(s.name, f"{', '.join(x['label'] for x in hit) or sys.argv[3]}: last {pct:g}% cut, slowed to fit (asked in the chat)")
        print(f"trimmed {len(hit)} shot(s); the edit rebuilds within a minute" if hit else "no such shot")
    elif cmd == "transition":                              # transition <song> <label> <name and params>: the transition INTO that shot
        p = os.path.join(FILM, "projects", sys.argv[2], sys.argv[2] + ".shots.txt")
        rows, n = open(p, encoding="utf-8").read().split("\n"), 0
        for i, ln in enumerate(rows):
            f = ln.split("|")
            if len(f) >= 4 and f[3].strip().startswith(sys.argv[3]):
                f[2] = " " + " ".join(sys.argv[4:]) + " "
                rows[i], n = "|".join(f), n + 1
        if n:
            shutil.copyfile(p, p + time.strftime(".%Y%m%d-%H%M%S.bak"))
            open(p, "w", encoding="utf-8", newline="\n").write("\n".join(rows))
            sh([EXE, os.path.join(FILM, "song_jobs.py"), sys.argv[2]], cwd=FILM, text=True, timeout=180)
            s = Song(sys.argv[2], "auto")
            s.rv["build_sig"] = None
            s.save()
            log(sys.argv[2], f"transition into {sys.argv[3]} set to {' '.join(sys.argv[4:])} (asked in the chat)")
        print(f"set on {n} shot(s); the edit rebuilds within a minute" if n else "no such shot")
    elif cmd == "lock":                                    # lock <song> <label> <run> <slot> <in> <out>
        s = Song(sys.argv[2], "auto")
        x = next(x for x in s.plan["shots"] if x["label"].startswith(sys.argv[3]) and "run" in x)
        key = f"{x['run']}:{x['slot']}"
        s.rv["locked"][key] = {"run": sys.argv[4], "slot": int(sys.argv[5]), "in": float(sys.argv[6]), "out": float(sys.argv[7]), "why": "Justice's pick"}
        s.rv["build_sig"] = None
        s.save()
        log(s.name, f"{x['label']}: locked to {sys.argv[4]}:{sys.argv[5]} {sys.argv[6]}-{sys.argv[7]} s (Justice's pick, slowed to fill its time)")
    elif cmd == "rebuild":
        s = Song(sys.argv[2], "auto")
        s.rv["build_sig"] = None
        s.save()
        print("the edit rebuilds on the next check (within a minute, or right after the current render)")
    elif cmd == "review":                                  # short on purpose: the local AI reads this
        s = Song(sys.argv[2], "check")
        rows = [l for l in open(os.path.join(HERE, f"report_{s.name}.txt"), encoding="utf-8").read().splitlines()[4:]] if os.path.exists(os.path.join(HERE, f"report_{s.name}.txt")) else []
        done = [l for l in rows if "waiting" not in l]
        print(f"{s.name}: {s.rv.get('built_shots', 0)} of {len(s.plan.get('shots', []))} shots in the edit; transitions: "
              f"{'every cut (' + ', '.join(t.split()[0] for t in s.plan.get('within', [])) + ' inside scenes)' if s.plan.get('within') else 'only at scene changes'}; "
              f"shot ends cut at {s.plan.get('tail', 4.98)} s of 5")
        print("judged shots:\n" + "\n".join(l[:150] for l in done[:20]))
        ef = jload(os.path.join(s.pdir, "_edit_flags.json"), {})
        print("finished-edit check:", "every shot moves" if not ef.get("flags") else ", ".join(f["label"] for f in ef["flags"]))
        print("latest decisions:\n" + "\n".join(l[20:170] for l in open(os.path.join(LOGS, s.name + ".log"), encoding="utf-8").read().splitlines()[-8:]))
    elif cmd == "selftest":
        STATE["novision"] = True
        s = Song(sys.argv[2], "check")
        f = next(f for b, k, st, f in s.jobs if st == sys.argv[3])
        print(json.dumps(check_run(s.run_look(os.path.join(s.jdir, f)), sys.argv[3], os.path.join(s.jdir, f))["slots"]))
