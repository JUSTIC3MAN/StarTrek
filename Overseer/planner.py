#!/usr/bin/env python3
"""Star Trek PLANNER - a new song from one MP3 to a finished FilmCraft edit, with no Claude (Justice 2026-11-03).

Drop an MP3 into Overseer\\new_songs\\ (name it "Artist - Title.mp3"), or say "new song <path to mp3>" in the Star Trek
chat. Every Overseer tick (Comfort runs it between jobs) moves each new song one step, using the local AI (Ollama):

  1 SONGMAP  project folder FilmCraft\\projects\\<song>\\ with the MP3; SongMap makes the timing sheet (started if needed)
  2 STYLES   the local AI writes a style round: N pictures, each a DIFFERENT art style (the installed Krea 2 style
             LoRAs) and a DIFFERENT part of the lyrics (README.txt, Comfort\\CLAUDE.md section 16); Comfort renders them
             and they are copied to Preview\\<Artist - Song>\\
  3 PICK     Justice picks one: "pick <song> <label>" in the chat, or the label written into Overseer\\plans\\<song>.pick.txt.
             No pick after pick_wait_minutes: the vision AI scores every picture and the best one is used.
  4 PLAN     the local AI writes FilmCraft\\projects\\<song>\\<song>.shots.txt from the SongMap sheet in the picked style;
             song_jobs.py checks it and every error goes back to the AI (up to max_tries)
  5 GO       song_jobs.py --queue and "<song> auto" in songs.txt: from here the Overseer generates, checks, places every
             shot in FilmCraft at its SongMap time and builds the edit into Preview, as for every song.

State: Overseer\\plans\\<song>.json   Settings: Overseer\\planner.json   Log: Overseer\\logs\\<song>.log (shown in the interface)
Commands: tick | new <mp3> ["Artist - Title"] | pick <song> <label> | status [song] | restyle <song> | replan <song>
"""
import glob, json, os, re, shutil, subprocess, sys, time, traceback, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.dirname(HERE)
COMFORT, FILM, SONGMAP, PREVIEW = (os.path.join(ST, x) for x in ("Comfort", "FilmCraft", "SongMap", "Preview"))
PLANS, DROP, LOGS = os.path.join(HERE, "plans"), os.path.join(HERE, "new_songs"), os.path.join(HERE, "logs")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
EXE = sys.executable[:-5] + ".exe" if sys.executable.lower().endswith("pythonw.exe") else sys.executable
AUDIO = (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac")
SETTINGS = {"styles_count": 6, "pick_wait_minutes": 30, "max_tries": 4, "model": "", "num_ctx": 32768,
            "think": True, "size": "1376x768", "people": ""}


# ------------------------------------------------------------------ small helpers
def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(song, msg):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, song + ".log"), "a", encoding="utf-8") as f:
        f.write(f"{now()} planner: {msg}\n")


def jload(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def jsave(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    os.replace(p + ".tmp", p)


def settings():
    s = dict(SETTINGS)
    s.update(jload(os.path.join(HERE, "planner.json"), {}))
    return s


def slug(x):
    s = re.sub(r"[^a-z0-9]+", "_", x.lower()).strip("_")
    return s or "song"


def http(url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def comfort_cfg():
    return jload(os.path.join(COMFORT, "config.json"), {})


def put_inbox(name, text):
    """A job file into Comfort's inbox (written under a dot-name, then renamed: Comfort never reads half a file)."""
    inbox = os.path.join(COMFORT, "inbox")
    os.makedirs(inbox, exist_ok=True)
    tmp = os.path.join(inbox, "." + name)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, os.path.join(inbox, name))


def readme_part(start, end=None):
    t = open(os.path.join(ST, "README.txt"), encoding="utf-8").read()
    i = t.find(start)
    if i < 0:
        return ""
    j = t.find(end, i + len(start)) if end else -1
    return t[i: j if j > 0 else len(t)].strip()


def comfort_section(n):
    t = open(os.path.join(COMFORT, "CLAUDE.md"), encoding="utf-8").read()
    i = t.find(f"\n## {n}.")
    j = t.find("\n## ", i + 5)
    return t[i: j if j > 0 else len(t)].strip() if i >= 0 else ""


# ------------------------------------------------------------------ the local AI (Ollama)
def chat(system, user, want_json=False, tag="plan"):
    c = comfort_cfg()
    llm, st = c.get("llm", {}), settings()
    url = llm.get("url", "http://127.0.0.1:11434").rstrip("/")
    model = st["model"] or llm.get("model", "qwen3.6:27b")
    try:                                        # give the GPU to the language model; ComfyUI reloads for its next job
        http(c.get("comfy_url", "http://127.0.0.1:8189").rstrip("/") + "/free", {"unload_models": True, "free_memory": True}, 30)
    except Exception:
        pass
    body = {"model": model, "stream": False, "keep_alive": "2m", "think": bool(st["think"]),
            "options": {"temperature": 0.7, "num_ctx": int(st["num_ctx"])},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if want_json:
        body["format"] = "json"
    last = None
    for _ in range(2):
        try:
            msg = http(url + "/api/chat", body, timeout=2400).get("message", {})
            txt = msg.get("content", "") or ""
            if want_json:
                return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
            return txt
        except Exception as e:  # noqa: BLE001
            last = e
            body.pop("think", None)
    raise RuntimeError(f"local AI ({model}) did not answer: {last}")


def unload():
    c = comfort_cfg()
    llm, st = c.get("llm", {}), settings()
    try:
        http(llm.get("url", "http://127.0.0.1:11434").rstrip("/") + "/api/generate",
             {"model": st["model"] or llm.get("model", "qwen3.6:27b"), "keep_alive": 0}, 30)
    except Exception:
        pass


# ------------------------------------------------------------------ steps
def new(mp3, label=""):
    """Start a new song from an audio file. Returns the song name."""
    if not os.path.isfile(mp3) or not mp3.lower().endswith(AUDIO):
        raise SystemExit(f"not an audio file: {mp3}")
    stem = os.path.splitext(os.path.basename(mp3))[0]
    label = (label or stem).strip()
    artist, title = (label.split(" - ", 1) + [""])[:2] if " - " in label else ("", label)
    artist, title = artist.strip(), re.sub(r"\s*[\[(].*?[\])]\s*", " ", title).strip() or stem
    song = slug(title)
    base, n = song, 2
    while os.path.exists(os.path.join(PLANS, song + ".json")) or os.path.exists(os.path.join(FILM, "projects", song, song + ".shots.txt")):
        song, n = f"{base}_{n}", n + 1
    pdir = os.path.join(FILM, "projects", song)
    os.makedirs(pdir, exist_ok=True)
    fname = re.sub(r'[\\/:*?"<>|]+', "", title) + os.path.splitext(mp3)[1].lower()
    dst = os.path.join(pdir, fname)
    if os.path.abspath(mp3) != os.path.abspath(dst):
        shutil.copyfile(mp3, dst)
    st = {"song": song, "artist": artist, "title": title, "audio": fname, "stage": "songmap", "since": time.time(),
          "preview": os.path.join(PREVIEW, f"{artist} - {title}" if artist else title), "tries": 0}
    jsave(os.path.join(PLANS, song + ".json"), st)
    queue_songmap(st)
    log(song, f"new song '{label}' -> FilmCraft\\projects\\{song}\\{fname}; SongMap queued")
    return song


def songmap_alive():
    for f in (".alive.watcher", ".alive.worker"):
        p = os.path.join(SONGMAP, f)
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 60:
            return True
    return False


def start_songmap():
    py = os.path.join(SONGMAP, "venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(SONGMAP, "venv", "bin", "python")
    if os.path.exists(py) and not songmap_alive():
        subprocess.Popen([py, os.path.join(SONGMAP, "songmap.py")], cwd=SONGMAP, creationflags=NOWIN,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def queue_songmap(st):
    pdir = os.path.join(FILM, "projects", st["song"])
    job = {"songs": [{"song": os.path.join(pdir, st["audio"]), "copy_to": [pdir]}]}
    inbox = os.path.join(SONGMAP, "inbox")
    os.makedirs(inbox, exist_ok=True)
    tmp = os.path.join(inbox, f".plan_{st['song']}.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(job, f)
    os.replace(tmp, os.path.join(inbox, f"plan_{st['song']}.json"))
    start_songmap()


def sheet_paths(st):
    pdir = os.path.join(FILM, "projects", st["song"])
    stem = os.path.splitext(st["audio"])[0]
    txt, js = os.path.join(pdir, stem + ".songmap.txt"), os.path.join(pdir, stem + ".songmap.json")
    if not os.path.exists(js):                   # SongMap names files after the song; take the one that is there
        hits = glob.glob(os.path.join(pdir, "*.songmap.json"))
        if hits:
            js = hits[0]
            txt = js[:-5] + ".txt"
    return txt, js


def installed_styles():
    comfy = comfort_cfg().get("comfy_dir") or os.path.join(ST, "ClaudeComfy", "ComfyUI")
    names = sorted(os.path.basename(p)[:-len("-comfy.safetensors")] for p in glob.glob(os.path.join(comfy, "models", "loras", "*-comfy.safetensors")))
    return names


def step_styles(st):
    txt, _ = sheet_paths(st)
    sheet = open(txt, encoding="utf-8").read()
    styles, n = installed_styles(), int(settings()["styles_count"])
    if len(styles) < 2:
        raise RuntimeError("no Krea 2 style LoRAs found in ComfyUI\\models\\loras (run the setup's model download)")
    system = ("You plan the look of a music video for Justice's Star Trek production. Follow these rules exactly.\n\n"
              + readme_part("THE GOAL", "WHAT \"DONE\"") + "\n\n" + comfort_section(16))
    user = f"""Song: "{st['title']}"{' by ' + st['artist'] if st['artist'] else ''}.
Its SongMap sheet (sections, timeline with the lyrics on timestamps, musical changes):
{sheet}

Write a STYLE ROUND of exactly {n} pictures so Justice can choose the song's art style.
- Each picture uses a DIFFERENT style from this list of installed Krea 2 style LoRAs (exact names), from different families,
  the ones that suit this song best: {', '.join(styles)}
- Each picture takes its inspiration from a DIFFERENT part of the lyrics (intro, each verse, chorus, bridge, outro): a
  different subject and moment. Art is an extended metaphor: make the viewer feel the line, never act it out literally.
  Keep the song's own culture and world. Never photoreal. Built-in motion (wind, water, smoke, light, cloth).
- Each prompt in this order: subject and action, then a style sentence written for that style, then composition (camera,
  framing, what stays empty), lighting, concrete colours. State clothing for any figure. 40-90 words. No text in the picture.
Answer JSON only:
{{"concept": "one sentence: the visual idea of the whole video",
  "people": "who may appear in this song's shots (or 'no people')",
  "sound": "one sentence of natural sounds that fit the song's world",
  "pictures": [{{"label": "short_snake_case_subject", "style": "<exact style name>", "section": "verse 1", "time": 34.2,
                 "lyric": "the line it comes from", "style_sentence": "the style sentence used in this prompt, word for word",
                 "palette": "its colours, e.g. ochre, rust red and ink black", "prompt": "..."}}]}}"""
    plan = chat(system, user, want_json=True)
    pics, used = [], set()
    for p in plan.get("pictures", []):
        sty, lab = str(p.get("style", "")).strip(), slug(str(p.get("label", "")))[:30]
        if sty in styles and sty not in used and lab and p.get("prompt"):
            used.add(sty)
            pics.append({**p, "style": sty, "label": lab})
    if len(pics) < 2:
        raise RuntimeError("the local AI did not return a usable style round")
    v = st.get("styles_round", 0) + 1
    job = f"{st['song']}_styles_v{v}"
    lines = [f"#name {job}", f"#size {settings()['size']}", "#n 1", "#seed random", "#style none"]
    for p in pics:
        trig = p["style"].replace("-", " ") + " style"
        prompt = re.sub(r"\s+", " ", str(p["prompt"])).strip().rstrip(".")
        lines.append(f"[label={p['label']}__{p['style']} lora={p['style']}-comfy.safetensors:1.1] {prompt}, no text, no watermark, {trig}")
    put_inbox(f"0_{job}.txt", "\n".join(lines) + "\n")
    brief_dir = os.path.join(COMFORT, "songs", os.path.basename(st["preview"]))
    os.makedirs(brief_dir, exist_ok=True)
    with open(os.path.join(brief_dir, "brief.md"), "a", encoding="utf-8") as f:
        f.write(f"# {os.path.basename(st['preview'])} - style round v{v} (local AI, {now()})\n\nConcept: {plan.get('concept', '')}\n"
                f"People: {plan.get('people', '')}\n\n" + "".join(
                    f"## {p['label']} - {p['style']}\nLyric ({p.get('section', '')}, {p.get('time', '')} s): {p.get('lyric', '')}\n\n{p['prompt']}\n\n" for p in pics))
    st.update({"stage": "styles", "styles_round": v, "styles_job": job, "styles": pics, "concept": plan.get("concept", ""),
               "people": plan.get("people", ""), "sound": plan.get("sound", ""), "since": time.time()})
    log(st["song"], f"style round v{v}: {len(pics)} pictures queued ({', '.join(p['style'] for p in pics)})")


def styles_done(st):
    d = os.path.join(COMFORT, "out", st["styles_job"], "_done.txt")
    if not os.path.exists(d):
        return None
    first = open(d, encoding="utf-8").readline()
    return "ok" if first.startswith("OK") else "failed"


def step_styles_wait(st):
    r = styles_done(st)
    if r is None:
        return
    if r == "failed":
        log(st["song"], "style round failed in Comfort - writing a new one")
        st["stage"] = "songmap_ready"
        return
    os.makedirs(st["preview"], exist_ok=True)
    out = os.path.join(COMFORT, "out", st["styles_job"])
    pics = sorted(glob.glob(os.path.join(out, "*.png")))
    for p in pics:
        shutil.copyfile(p, os.path.join(st["preview"], f"styles v{st['styles_round']} {os.path.basename(p)}"))
    st["style_files"] = pics
    st.update({"stage": "pick", "since": time.time()})
    labels = ", ".join(p["label"] for p in st["styles"])
    log(st["song"], f"style round ready in Preview\\{os.path.basename(st['preview'])}. Pick one: say 'pick {st['song']} <label>' "
                    f"in the chat ({labels}). No pick in {settings()['pick_wait_minutes']} min: the vision AI picks the best.")


def pick_file(st):
    p = os.path.join(PLANS, st["song"] + ".pick.txt")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def chosen(st, word):
    word = slug(word)
    return next((p for p in st["styles"] if word and (p["label"].startswith(word) or p["style"].startswith(word) or word in p["label"])), None)


def step_pick(st):
    want = st.get("pick") or pick_file(st)
    choice = chosen(st, want) if want else None
    if want and not choice:
        log(st["song"], f"pick '{want}' matches no picture of the style round")
    if not choice and time.time() - st["since"] < 60 * float(settings()["pick_wait_minutes"]):
        return
    if not choice:                                # nobody picked: the vision AI chooses
        sys.path.insert(0, HERE)
        import overseer
        best, scores = None, []
        files = st.get("style_files", [])
        for i, p in enumerate(st["styles"]):
            f = next((x for x in files if p["label"] in os.path.basename(x)), None) or (files[i] if i < len(files) else None)
            if not f:
                continue
            a = overseer.vlm(f, f"This picture is one option for the art style of a music video for the song '{st['title']}' "
                                f"(concept: {st.get('concept', '')}). Judge it as a frame for a big concert screen. "
                                'Answer JSON {"beauty": 1-10, "people_problem": true/false, "text_or_border": true/false, "why": "short"}')
            if a:
                sc = float(a.get("beauty", 0) or 0) - (3 if a.get("people_problem") else 0) - (3 if a.get("text_or_border") else 0)
                scores.append(f"{p['label']} {sc:g}")
                if best is None or sc > best[0]:
                    best = (sc, p)
        overseer.vlm_unload()
        choice = best[1] if best else st["styles"][0]
        log(st["song"], f"no pick from Justice - the vision AI chose {choice['label']} ({'; '.join(scores) or 'no scores'})")
    else:
        log(st["song"], f"Justice picked {choice['label']} ({choice['style']})")
    st.update({"picked": choice, "stage": "plan", "tries": 0})


def style_line(st):
    """The shot list's style K line from the picked picture: LoRA | style words | palette | trigger | look."""
    p = st["picked"]
    sty = p["style"]
    words = sty.replace("-", " ")
    sentence = re.sub(r"\s+", " ", str(p.get("style_sentence") or "")).strip(" ,.")
    if not sentence:                               # fall back to the part of the prompt that names the style
        m = re.search(r"([^,.]*" + re.escape(words.split()[-1]) + r"[^.]*)", str(p["prompt"]), re.I)
        sentence = (m.group(1).strip() if m else words).rstrip(",")
    palette = re.sub(r"\s+", " ", str(p.get("palette") or "")).strip(" ,.") or "the colours of the picked picture"
    clean = lambda x: x.replace("|", "/")
    return f"style K | lora={sty}-comfy.safetensors:1.1 | {clean(sentence)} | {clean(palette)} | {words} style | {clean(sentence)}, {clean(palette)}"


def header(st, sheet_json):
    pdir_rel = os.path.basename(sheet_json)
    people = settings()["people"] or st.get("people") or "no people"
    no_people = people.lower().startswith("no ")
    name = os.path.basename(st["preview"])
    return "\n".join([
        f"#title {name}",
        f"#songmap {pdir_rel}",
        f"#music {st['audio']}",
        f"#queue {st['song'][0]}",
        "#kind music-video",
        "#neg no text, no letters, no watermark, no border, no frame, no blank paper, no photoreal",
        f"#subject2 {'no people appear anywhere.' if no_people else 'the people shown: ' + people + '; mostly seen from behind or far away; never a face close to the camera.'}",
        *([] if no_people else [f"#people {people}"]),
        f"#sound {st.get('sound') or 'Natural sounds that fit each shot.'}",
        style_line(st),
        f"# planned by the local AI {now()} - concept: {st.get('concept', '')}",
        f"#pics {st['song']}_v1",
        "#build overseer",
        "#musicfull off",
        "#fadein 18",
        "#fadeout 90",
        "#inpoint 1.2",
        f"#copy {os.path.join(st['preview'], name + ' (full song).mp4')}",
    ]) + "\n"


def step_plan(st):
    txt, js = sheet_paths(st)
    sheet = open(txt, encoding="utf-8").read()
    head = header(st, js)
    fmt = open(os.path.join(FILM, "song_jobs.py"), encoding="utf-8").read().split('"""')[1]
    ex_path = os.path.join(HERE, "planner_example.shots.txt")
    example = open(ex_path, encoding="utf-8").read() if os.path.exists(ex_path) else ""
    system = ("You write the shot list of a music video for Justice's Star Trek production. It is turned into AI pictures, "
              "MiniMax H3 videos and a FilmCraft edit with no human in between, so follow the format and the rules exactly.\n\n"
              + readme_part("THE GOAL", "WHERE THINGS ARE") + "\n\nSHOT LIST FORMAT (song_jobs.py):\n" + fmt
              + "\n\nA FINISHED EXAMPLE (another song; it reuses older runs, which a new song never does):\n" + example)
    pdir = os.path.join(FILM, "projects", st["song"])
    shots = os.path.join(pdir, st["song"] + ".shots.txt")
    err = st.get("last_error", "")
    user = f"""Song: "{st['title']}"{' by ' + st['artist'] if st['artist'] else ''}. Concept: {st.get('concept', '')}
Picked look (style key K): {st['picked']['style']} - the picture Justice's team chose: {st['picked']['prompt']}

Its SongMap sheet:
{sheet}

The header is already written (do not repeat it):
{head}
Write ONLY the body of the shot list for the WHOLE song, from 0 to its end:
- "batch 1" first; start a new "batch N" about every 40-60 seconds of song.
- "@ <seconds> <section name - the scene>" at each section start from the sheet (and at every big drop); each section is
  ONE scene (one place, one light) and the scene CHANGES at each @.
- Shot lines: LEN | SRC | TRANSITION | label | subject ; framing | motion
  LEN in bars (1, 2, 3, 4) or "*" for the last shot before the next @. Long moving shots in intro, verses, bridge and outro
  (2-4 bars); faster in choruses (1-2 bars). Never one fixed length.
  SRC is always K (a new picture and shot in the picked style). Never "=label", never reuse a shot.
  TRANSITION: empty on the first shot of the song, otherwise a real transition chosen by what the two shots share
  (motion: cross_zoom 12 strength=30 / push 14 / whip 12; light: luma_fade 14 / flare 14 / light_leak 24; paint or paper:
  film_dissolve 14; mist or water: blur_dissolve 14 blur=30 / wave 18), loud ones only on a hard hit, inside one scene
  mostly film_dissolve 14 or blur_dissolve 14.
  label: a letter per section + number + short words (a01_sea_wide, b03_lantern_close); every label unique.
  subject: what the picture shows, as metaphor for that part of the lyrics, in the picked style's world, with clothing for
  any figure; framing: the camera distance and angle (vary them: wide, close, low, from behind, high); motion: what
  moves the whole time and how the camera moves (one continuous move, never still).
- Plain text only, one line per shot, no numbering, no commentary.
{('YOUR LAST ATTEMPT FAILED THE CHECK. Fix exactly this and write the whole body again: ' + err) if err else ''}"""
    body = chat(system, user, tag="plan")
    m = re.search(r"```[a-z]*\n(.*?)```", body, re.S)
    body = (m.group(1) if m else body).strip()
    keep = [l for l in body.splitlines() if l.strip() and (l.startswith(("batch", "@", "#")) or l.count("|") >= 4)]
    with open(shots, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n".join(keep) + "\n")
    r = subprocess.run([EXE, os.path.join(FILM, "song_jobs.py"), st["song"]], cwd=FILM, capture_output=True, text=True,
                       timeout=300, creationflags=NOWIN)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    st["tries"] = st.get("tries", 0) + 1
    if r.returncode == 0 and out.startswith(st["song"] + ":"):
        st.update({"stage": "go", "last_error": "", "check": out.splitlines()[0]})
        log(st["song"], "shot list written and checked: " + out.splitlines()[0])
        return
    st["last_error"] = out[-600:]
    log(st["song"], f"shot list try {st['tries']} failed the check: {out[-300:]}")
    if st["tries"] >= int(settings()["max_tries"]):
        st["stage"] = "stuck"
        log(st["song"], "STUCK: the local AI could not write a valid shot list. Fix the shot list by hand or say 'replan " + st["song"] + "'.")


def step_go(st):
    r = subprocess.run([EXE, os.path.join(FILM, "song_jobs.py"), st["song"], "--queue"], cwd=FILM, capture_output=True,
                       text=True, timeout=300, creationflags=NOWIN)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode:
        st.update({"stage": "plan", "last_error": out[-600:]})
        log(st["song"], "queueing failed, back to planning: " + out[-300:])
        return
    rows = [l for l in open(os.path.join(HERE, "songs.txt"), encoding="utf-8").read().splitlines() if l.split()[:1] != [st["song"]]] \
        if os.path.exists(os.path.join(HERE, "songs.txt")) else []
    rows.append(f"{st['song']} auto")
    with open(os.path.join(HERE, "songs.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    st.update({"stage": "producing", "since": time.time()})
    log(st["song"], "queued in Comfort and set to auto in songs.txt - the Overseer now produces and builds the edit")


# ------------------------------------------------------------------ the tick
def tick():
    os.makedirs(DROP, exist_ok=True)
    for f in sorted(os.listdir(DROP)):           # 1. new MP3s dropped into Overseer\new_songs
        p = os.path.join(DROP, f)
        if os.path.isfile(p) and f.lower().endswith(AUDIO):
            try:
                new(p)
                os.makedirs(os.path.join(DROP, "started"), exist_ok=True)
                shutil.move(p, os.path.join(DROP, "started", f))
            except Exception as e:  # noqa: BLE001
                log("planner", f"could not start {f}: {e}")
    used_ai = False
    for pf in sorted(glob.glob(os.path.join(PLANS, "*.json"))):
        st = jload(pf, None)
        if not st or st.get("stage") in ("producing", "stuck"):
            continue
        try:
            stage = st["stage"]
            if stage == "songmap":
                txt, js = sheet_paths(st)
                if os.path.exists(txt) and os.path.exists(js):
                    st["stage"] = "songmap_ready"
                    log(st["song"], "SongMap sheet ready")
                elif time.time() - st["since"] > 300:
                    start_songmap()                  # make sure SongMap is running
            if st["stage"] == "songmap_ready" and not used_ai:
                step_styles(st)
                used_ai = True
            elif st["stage"] == "styles":
                step_styles_wait(st)
            elif st["stage"] == "pick":
                step_pick(st)
            if st["stage"] == "plan" and not used_ai:
                step_plan(st)
                used_ai = True
            if st["stage"] == "go":
                step_go(st)
        except Exception:
            log(st["song"], "planner error: " + traceback.format_exc()[-600:].replace("\n", " | "))
        jsave(pf, st)
    if used_ai:
        unload()


def status(song=None):
    out = []
    for pf in sorted(glob.glob(os.path.join(PLANS, "*.json"))):
        st = jload(pf, {})
        if song and st.get("song") != song:
            continue
        line = f"{st.get('song')}: {st.get('stage')}"
        if st.get("stage") == "pick":
            line += " - pick one of: " + ", ".join(p["label"] for p in st.get("styles", []))
        if st.get("picked"):
            line += f" | look: {st['picked']['style']}"
        if st.get("check"):
            line += " | " + st["check"]
        out.append(line)
    return "\n".join(out) or "no new songs"


def cli(argv):
    cmd = argv[0] if argv else "tick"
    if cmd == "tick":
        tick()
    elif cmd == "new":
        print("started " + new(argv[1], " ".join(argv[2:])) + " - the Overseer takes it from here")
    elif cmd == "pick":
        pf = os.path.join(PLANS, argv[1] + ".json")
        st = jload(pf, None)
        if not st:
            print("no new song called " + argv[1])
            return
        c = chosen(st, " ".join(argv[2:])) if st.get("styles") else None
        if not c:
            print("no such picture; choose from: " + ", ".join(p["label"] for p in st.get("styles", [])))
            return
        st["pick"] = c["label"]
        jsave(pf, st)
        print(f"{argv[1]}: picked {c['label']} ({c['style']}) - the shot list is written at the next tick")
    elif cmd in ("restyle", "replan"):
        pf = os.path.join(PLANS, argv[1] + ".json")
        st = jload(pf, None)
        if not st:
            print("no new song called " + argv[1])
            return
        st.update({"stage": "songmap_ready" if cmd == "restyle" else "plan", "tries": 0, "last_error": "", "pick": ""})
        jsave(pf, st)
        print(f"{argv[1]}: {'a new style round' if cmd == 'restyle' else 'a new shot list'} at the next tick")
    elif cmd in ("status", "planstatus"):
        print(status(argv[1] if len(argv) > 1 else None))
    else:
        print(__doc__)


if __name__ == "__main__":
    cli(sys.argv[1:])
