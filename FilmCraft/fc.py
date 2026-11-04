#!/usr/bin/env python3
"""fc: compact front end for FilmCraft. Claude writes a short cut list; this does the rest.

  python fc.py scan <dir> [dir...]   index videos -> clips.tsv, prints one short line per clip
  python fc.py build <cut.txt>       cut list -> FilmCraft project + rendered video (one-line result)
  python fc.py peek <video> [secs..] frame strip PNG (default: around each cut) for a quick look

Cut list (one instruction per line, # comments):
  out renders/name.mp4        output (relative to this folder); project saved next to it as .fcproj
  size 1080x1920@30           optional; default = first clip's size and fps
  fit fill|fit|none           how off-size clips are scaled (default fill)
  fadein 15                   frames: video from black + audio fade in
  clip c03 | clip <path> [a-b]  add a clip (id from clips.tsv or a path), optional trim in seconds
  clip <path> noramp          leave this clip's speed exactly as rendered
  > glitch 12                 transition into the next clip (name or FilmCraft id, frames)
  > whip 15 direction=east blur=90   ... plus that transition's params (transitions.txt lists them all)
  speed 7.5-9.4 160           that part (clip seconds) of the clip above at 160 %, with smooth slopes
  ramp off | ramp 0.6 | ramp free   speed ramps run on EVERY clip by default (strength 0.85), keeping each clip's cut length;
                              free = let ramped clips get shorter (old behaviour)
  fadeout 20                  frames: video to black + audio fade out
  text "KWOTE" 2.3-5.1 style=boss pos=lower-left   title over the clip above, in its seconds (2.3- = to its end);
                              on V2 (V3.. when titles overlap); style props can follow: size=120 font=Impact fade=12
  subs lyrics.srt style=lyrics [offset=2.5]   .srt -> Subtitle caption track with one style, burned into the export
  (a cut list whose first line says 'built by song_cut.py' is rewritten from <song>.plan.json at every build)
  copy A:\\Preview\\x.mp4      after the render, a copy of the finished video there (as many as needed)
  music song.mp3 [at=0]       the song on A2 from that sequence second (path relative to the cut list, or full),
                              trimmed to the end of the edit (fadeout fades it too); no clips yet = project only
Title/subtitle styles and named positions (lower-left lower-third center top-left top-right): titles.json

Speed ramps: each clip's motion is measured (ramp.py, cached in _motion/ next to the cut list) and stalls
are sped up with gradual slopes, as constant-speed pieces with frame blending. Report: <out>.ramps.txt
"""
import json, math, os, re, shlex, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TICK = 254016000000
WIN = os.name == "nt"
# Windows folder -> mount name in the Linux shell (Cowork sessions). Add folders here as needed.
MOUNTS = {r"A:\Ai projects\Star Trek": "Star Trek", r"A:\artcraft\FilmCraft": "FilmCraft", r"A:\artcraft": "artcraft", r"A:\Ai projects\Comfort": "Comfort", r"A:\Ai projects": "Ai projects"}
ALIAS = {"fade": "dip_to_black", "black": "dip_to_black", "white": "dip_to_white", "dissolve": "cross_dissolve",
         "film": "film_dissolve", "vhs": "vhs_damage", "leak": "light_leak", "chroma": "chroma_leak",
         "zoom": "zoom_blur", "czoom": "cross_zoom", "burn": "burn_chroma", "blur": "blur_dissolve",
         "spin": "spin_3d", "lens": "lens_blur"}
VIDEXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def cli():
    if WIN:
        return os.path.join(HERE, "filmcraft-cli.exe")
    for d in sorted(os.listdir(os.path.join(HERE, "tools")), reverse=True):
        p = os.path.join(HERE, "tools", d, "bin", "filmcraft-cli")
        if d.startswith("linux-") and os.path.exists(p):
            return p
    sys.exit("no Linux filmcraft-cli in tools/linux-*")


def mnt_root():
    return os.path.join(os.path.expanduser("~"), "mnt")


def to_local(p):
    """Windows path -> path usable here (identity on Windows)."""
    p = p.strip().strip('"')
    if WIN or not (len(p) > 1 and p[1] == ":"):
        return p if os.path.isabs(p) else os.path.join(HERE, p)
    for w, name in MOUNTS.items():   # first mapping whose folder is connected in this session wins
        if p.lower().startswith(w.lower()) and os.path.isdir(os.path.join(mnt_root(), name)):
            return os.path.join(mnt_root(), name, p[len(w):].lstrip("\\/").replace("\\", "/"))
    sys.exit(f"no mount for {p}: add it to MOUNTS in fc.py")


def to_win(p):
    if WIN:
        return p
    root = mnt_root() + os.sep
    if p.startswith(root):
        name, _, rest = p[len(root):].partition("/")
        for w, n in MOUNTS.items():
            if n == name:
                return w + ("\\" + rest.replace("/", "\\") if rest else "")
    return p


def fc(*args):
    r = subprocess.run([cli(), *args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def media_info(proj):
    items = json.load(open(proj, encoding="utf-8"))["project"]["items"]
    out = {}
    for k, it in items.items():
        m = it.get("kind", {}).get("Media")
        if not m:
            continue
        info, v = m["info"], m["info"].get("video") or {}
        fr = v.get("frame_rate") or {"num": 30, "den": 1}
        out[int(k)] = {"path": m["media"]["File"]["path"], "sec": info["duration"] / TICK,
                       "w": v.get("width"), "h": v.get("height"), "fps": fr["num"] / fr["den"],
                       "audio": bool(info.get("audio_streams") or info.get("audio"))}
    return out


def import_media(paths, proj):
    code, out, err = fc("--save-as", proj, "import", *paths)
    if code:
        sys.exit("import failed: " + (err or out).strip()[:300])
    return json.loads(out)["items"]


# ---------- scan ----------
def scan(dirs):
    files = []
    for d in dirs:
        for root, _, names in os.walk(to_local(d)):
            files += [os.path.join(root, n) for n in names if n.lower().endswith(VIDEXT)]
    if not files:
        sys.exit("no videos found")
    files.sort(key=os.path.getmtime, reverse=True)
    proj = os.path.join(HERE, "work", "scan.fcproj")
    os.makedirs(os.path.dirname(proj), exist_ok=True)
    ids = import_media(files, proj)
    info = media_info(proj)
    rows = []
    for n, (i, f) in enumerate(zip(ids, files), 1):
        m = info.get(i, {})
        rows.append([f"c{n:02d}", f"{m.get('sec', 0):.1f}", f"{m.get('w')}x{m.get('h')}",
                     f"{m.get('fps', 0):.4g}", "a" if m.get("audio") else "-",
                     time.strftime("%m-%d", time.localtime(os.path.getmtime(f))), to_win(f)])
    with open(os.path.join(HERE, "clips.tsv"), "w", encoding="utf-8") as fh:
        fh.write("\n".join("\t".join(r) for r in rows) + "\n")
    for r in rows[:15]:
        print(" ".join(r[:6]), os.path.basename(r[6].replace("\\", "/")))
    print(f"{len(rows)} clips -> clips.tsv (newest first{', 15 shown' if len(rows) > 15 else ''})")


def clip_path(ref):
    if ref.startswith("c") and ref[1:].isdigit():
        for line in open(os.path.join(HERE, "clips.tsv"), encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if f[0] == ref:
                return to_local(f[-1])
        sys.exit(f"{ref} not in clips.tsv (run scan)")
    return to_local(ref)


# ---------- build ----------
DIRS = {"north": "From North", "east": "From East", "south": "From South", "west": "From West"}
COMMENT = re.compile(r"(?:^|\s)#(?![0-9a-fA-F]{6}\b)")


def tr_params(tokens):
    """`key=value` words after a transition -> FilmCraft params (see transitions.txt for each one's params).
    direction=east  color=#ffb070  center=960,540 (pixels)  corner=top_left  amount=70  invert  reverse"""
    params, reverse = {}, False
    for tok in tokens:
        k, eq, v = tok.partition("=")
        if not eq:
            if k == "reverse":
                reverse = True
            else:
                params[k] = True
            continue
        lv = v.lower()
        if k == "direction" and lv in DIRS:
            params[k] = DIRS[lv]
        elif lv in ("true", "on", "yes", "false", "off", "no"):
            params[k] = lv in ("true", "on", "yes")
        elif "," in v:
            params[k] = [float(x) for x in v.split(",")]
        else:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v if v.startswith("#") else v.replace("_", " ")
    return params, reverse


def parse(cut):
    plan = {"out": "renders/out.mp4", "size": None, "fit": "fill", "fadein": 0, "fadeout": 0, "ramp": None, "ramp_keep": True, "seq": [], "subs": [], "music": None, "copy": []}  # ramps ON by default, clip lengths kept (Justice 2026-10-27)
    for raw in open(cut, encoding="utf-8"):
        line = COMMENT.split(raw)[0].strip()
        if not line:
            continue
        key, _, rest = line.partition(" ")
        rest = rest.strip()
        if key == "clip":
            trim, noramp = None, False
            if rest.endswith(" noramp"):
                rest, noramp = rest[:-7].rstrip(), True
            parts = rest.rsplit(" ", 1)
            if len(parts) == 2 and "-" in parts[1] and parts[1].replace("-", "").replace(".", "").isdigit():
                rest, (a, b) = parts[0], parts[1].split("-")
                trim = (float(a), float(b))
            plan["seq"].append({"path": clip_path(rest), "trim": trim, "noramp": noramp, "speed": []})
        elif key == ">":
            if not plan["seq"]:
                sys.exit("'>' must come after a clip")
            bits = rest.split()
            fr, extra = (int(bits[1]), bits[2:]) if len(bits) > 1 and bits[1].isdigit() else (12, bits[1:])
            params, rev = tr_params(extra)
            plan["seq"][-1]["tr"] = (ALIAS.get(bits[0], bits[0]), fr, params, rev)
        elif key == "speed":                      # speed 7.5-9.4 160  = that part of the clip above at 160 %
            if not plan["seq"]:
                sys.exit("'speed' must come after a clip")
            rng, _, pct = rest.partition(" ")
            a, b = rng.split("-")
            plan["seq"][-1]["speed"].append((float(a), float(b), float(pct) / 100))
        elif key == "ramp":                       # ramp off | ramp on | ramp 0.6 (strength) | ramp free (may shorten clips)
            if rest == "free":
                plan["ramp"], plan["ramp_keep"] = None, False
            else:
                plan["ramp"] = 0.0 if rest in ("off", "0") else (None if rest in ("on", "") else float(rest))
        elif key == "text":                       # text "KWOTE" 2.3-5.1 style=boss pos=lower-left
            if not plan["seq"]:
                sys.exit("'text' must come after a clip")
            plan["seq"][-1].setdefault("texts", []).append(parse_text(rest))
        elif key == "subs":                       # subs lyrics.srt style=lyrics
            plan["subs"].append(parse_subs(rest, cut))
        elif key == "copy":                       # copy A:\\folder\\name.mp4 = a copy of the finished video there
            plan["copy"].append(rest.strip().strip('"'))
        elif key == "clipaudio":                  # clipaudio off: the clips' own sound is left out (music videos: only the song)
            plan["clipaudio"] = rest.strip().lower() not in ("off", "no", "0", "false")
        elif key == "musicfull":                  # musicfull on: the whole song on A2, not trimmed to the end of the edit
            plan["musicfull"] = rest.strip().lower() in ("on", "yes", "1", "true")
        elif key == "music":                      # music song.mp3 [at=12.5]
            plan["music"] = parse_music(rest, cut)
        elif key in ("fadein", "fadeout"):
            plan[key] = int(rest or 15)
        elif key in ("out", "fit"):
            plan[key] = rest
        elif key == "size":
            wh, _, fps = rest.partition("@")
            w, h = wh.lower().split("x")
            plan["size"] = (int(w), int(h), float(fps or 30))
        else:
            sys.exit(f"unknown line: {line}")
    if not plan["seq"] and not plan["music"]:
        sys.exit("no clips")
    return plan


def ramp_plan(p, cut, seq_fps):
    """Speed ramps (ramp.py): measure each clip's motion and plan constant-speed pieces. Returns report lines."""
    import ramp as R
    cache = os.path.join(os.path.dirname(os.path.abspath(cut)), "_motion")
    seq, lines = p["seq"], []
    for i, c in enumerate(seq):
        s = 0.0 if c["noramp"] else (R.STRENGTH if p["ramp"] is None else p["ramp"])
        name = os.path.basename(c["path"])
        if s <= 0 and not c["speed"]:
            lines.append(f"{name}: ramp off")
            continue
        try:
            f = c["m"]["fps"]
            mo = R.motion(c["path"], cache)
            r = R.curve(mo, f, c["a"], c["b"], s, c["speed"])
            if r and p.get("ramp_keep", True) and not c["speed"]:
                r = R.keep_length(r)              # cut length kept: the edit stays on SongMap's beats
            if r:
                k = f / seq_fps                   # transitions sit on the first/last piece: keep those long enough
                head = (seq[i - 1]["tr"][1] if i and "tr" in seq[i - 1] else p["fadein"] if i == 0 else 0) * k
                tail = (c["tr"][1] if "tr" in c and i + 1 < len(seq) else p["fadeout"] if i == len(seq) - 1 else 0) * k
                c["pieces"] = R.pieces(r, f, int(math.ceil(head)), int(math.ceil(tail)))
            lines.append(f"{name}: " + R.describe(mo[int(round(c['a'] * f)):], r, f))
        except Exception as e:
            lines.append(f"{name}: ramp skipped ({e})")
    return lines


def clip_positions(proj):
    """clip id -> (start, duration) in ticks, read from the saved project."""
    out = {}

    def walk(x):
        if isinstance(x, dict):
            if "source_in" in x and "start" in x and "id" in x and "duration" in x:
                out[x["id"]] = (x["start"], x["duration"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(json.load(open(proj, encoding="utf-8")))
    return out


# ---------- titles and subtitles: text / subs lines (2026-10-26) ----------
def conv(v):
    """key=value value -> bool / int / float / [floats] / str"""
    lv = v.lower()
    if lv in ("true", "on", "yes", "false", "off", "no"):
        return lv in ("true", "on", "yes")
    for f in (int, float):
        try:
            return f(v)
        except ValueError:
            pass
    if re.fullmatch(r"-?[\d.]+(?:,-?[\d.]+)+", v):
        return [float(x) for x in v.split(",")]
    return v


def kv_opts(tokens, what):
    d = {}
    for tok in tokens:
        k, eq, v = tok.partition("=")
        if not eq or not k:
            sys.exit(f"{what}: expected key=value, got {tok}")
        d[k] = conv(v)
    return d


def parse_text(rest):
    """text "KWOTE" 2.3-5.1 style=boss pos=lower-left [prop=value ...]  (seconds from the start of the clip above)"""
    try:
        toks = shlex.split(rest)
    except ValueError as e:
        sys.exit(f"text: {e}")
    if not toks:
        sys.exit("text: nothing to show")
    a, b, kv = 0.0, None, []
    for tok in toks[1:]:
        m = re.fullmatch(r"(\d*\.?\d+)-(\d*\.?\d+|end)?", tok)
        if m:
            a, b = float(m[1]), (float(m[2]) if m[2] and m[2] != "end" else None)
        else:
            kv.append(tok)
    return {"text": toks[0].replace("\\n", "\n"), "a": a, "b": b, "opts": kv_opts(kv, "text")}


def parse_subs(rest, cut):
    """subs lyrics.srt style=lyrics [offset=2.5]  (path relative to the cut list, or a full path)"""
    toks, kv = rest.split(), []
    while len(toks) > 1 and re.fullmatch(r"\w+=\S*", toks[-1]):
        kv.insert(0, toks.pop())
    path = " ".join(toks).strip('"')
    loc = os.path.join(os.path.dirname(os.path.abspath(cut)), path)
    if not os.path.exists(loc):
        loc = to_local(path)
    if not os.path.exists(loc):
        sys.exit(f"subs: no file {path}")
    return {"path": loc, "opts": kv_opts(kv, "subs")}


def parse_music(rest, cut):
    """music song.mp3 [at=0]  (path relative to the cut list, or a full path)"""
    toks, at = rest.split(), 0.0
    if len(toks) > 1 and toks[-1].startswith("at="):
        at = float(toks.pop()[3:])
    path = " ".join(toks).strip('"')
    loc = os.path.join(os.path.dirname(os.path.abspath(cut)), path)
    if not os.path.exists(loc):
        loc = to_local(path)
    if not os.path.exists(loc):
        sys.exit(f"music: no file {path}")
    return {"path": loc, "at": at}


def read_srt(path):
    ts, cues = r"(\d+):(\d+):(\d+)[,.](\d+)", []
    sec = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 10 ** len(ms)
    txt = open(path, encoding="utf-8-sig", errors="replace").read().replace("\r", "")
    for block in re.split(r"\n\s*\n", txt.strip()):
        lines = block.split("\n")
        for i, l in enumerate(lines):
            m = re.match(rf"\s*{ts}\s*-->\s*{ts}", l)
            if m:
                body = re.sub(r"<[^>]+>|\{\\[^}]*\}", "", "\n".join(lines[i + 1:])).strip()
                if body:
                    cues.append((sec(*m.groups()[:4]), sec(*m.groups()[4:]), body))
                break
    return cues


def load_titles():
    try:
        return json.load(open(os.path.join(HERE, "titles.json"), encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"titles.json: {e}")


def pick_font(fonts, fam, sty, fallback):
    """Installed family/style for a style's font, else its fallback. Returns (family, style, note or None)."""
    if not fonts or not fam:
        return fam, sty, None
    f = {x["family"].lower(): x for x in fonts}.get(fam.lower())
    if not f:
        fb = fallback or ["Inter", "Bold"]
        near = [x["family"] for x in fonts if x["family"].lower().startswith(fam.split()[0].lower())][:5]
        return fb[0], (fb[1] if len(fb) > 1 and sty else None), f"{fam} missing->{fb[0]}" + (f" (have: {', '.join(near)})" if near else "")
    styles = f["styles"] or ["Regular"]
    low = {s.lower(): s for s in styles}
    if not sty or sty.lower() in low:
        return f["family"], low.get((sty or "").lower(), sty), None
    for s in ("bold", "black", "heavy", "extrabold", "semibold", "regular"):
        if s in low:
            return f["family"], low[s], f"{fam} {sty} missing->{low[s]} (has {', '.join(styles)})"
    return f["family"], styles[0], f"{fam} {sty} missing->{styles[0]}"


def title_tracks(p):
    """Give each text line a video track (1 = V2) so overlapping titles stack. Returns the sequence's video track count."""
    t, ends = 0.0, []
    for c in p["seq"]:
        ln = c["b"] - c["a"]
        for x in c.get("texts", []):
            s, e = t + x["a"], t + (ln if x["b"] is None else min(x["b"], ln))
            for i, end in enumerate(ends):
                if end <= s + 1e-6:
                    ends[i], x["track"] = e, i + 1
                    break
            else:
                ends.append(e)
                x["track"] = len(ends)
        t += ln
    return max(2, 1 + len(ends))


def add_titles(proj, p, pos, w, h, fps):
    """text lines -> styled graphics clips over their clips; subs lines -> Subtitle caption tracks.
    Returns (position + fade steps for the effects pass, count note, font notes)."""
    items = [(c, x) for c in p["seq"] for x in c.get("texts", [])]
    if not items and not p["subs"]:
        return [], "", ""
    cfg = load_titles()
    S, POS = cfg.get("styles", {}), cfg.get("positions", {})
    k, fr = min(w / 1920, h / 1080), TICK / fps
    s1, made, subs, notes = [("fonts.list", {"system": True})], [], [], []

    def style(o, default):
        o = dict(o)
        name = o.pop("style", default)
        if name not in S:
            sys.exit(f"no style '{name}' in titles.json")
        st = {a: v for a, v in S[name].items() if not a.startswith("_")}
        st.update(o)
        return name, st
    for c, x in items:
        name, st = style(x["opts"], cfg.get("default_style", "clean"))
        if st.pop("captions", False):
            sys.exit(f"style '{name}' is a subtitle style: use it on a subs line")
        c0 = pos[c["v"][0]][0]
        clen = round((pos[c["v"][-1]][0] + pos[c["v"][-1]][1] - c0) / fr)
        fa = min(round(x["a"] * fps), clen)
        fb = clen if x["b"] is None else min(round(x["b"] * fps), clen)
        if fb - fa < 2:
            notes.append(f"'{x['text']}' skipped (outside its clip)")
            continue
        st["size"] = round(st.get("size", 100) * k, 1)
        made.append((x, st, fb - fa))
        s1.append(("graphics.newText", {"text": x["text"], "position": [w / 2, h / 2], "size": st["size"],
                                        "seconds": (fb - fa) / fps, "track": x["track"], "time": round((round(c0 / fr) + fa) * fr)}))
    for sb in p["subs"]:
        name, st = style(sb["opts"], "lyrics")
        st.pop("captions", None)
        off = float(st.pop("offset", 0))
        tr = {"format": "Subtitle", "name": st.pop("name", os.path.splitext(os.path.basename(sb["path"]))[0])}
        if "language" in st:
            tr["language"] = st.pop("language")
        subs.append((st, read_srt(sb["path"]), off))
        s1.append(("captions.newTrack", tr))
    _, r1, _ = run_steps(proj, s1)
    fonts = r1[0].get("result") or []
    ids = [r["result"]["clip"] for r in r1[1:1 + len(made)]]
    tracks = [r["result"]["track"] for r in r1[1 + len(made):]]
    s2 = []
    for (x, st, n), cid in zip(made, ids):
        fam, sty, note = pick_font(fonts, st.get("font"), st.get("font_style"), st.get("fallback"))
        if note and note not in notes:
            notes.append(note)
        props = {a: v for a, v in st.items() if a not in ("pos", "fade", "fallback", "font", "font_style")}
        if fam:
            props["font"] = fam
        if sty:
            props["font_style"] = sty
        s2 += [("graphics.set", {"clip": cid, "layer": 0, "props": props}), ("graphics.list", {"clip": cid})]
    for (st, cues, off), tr in zip(subs, tracks):
        fam, _, note = pick_font(fonts, st.get("font"), None, st.get("fallback"))
        if note and note not in notes:
            notes.append(note)
        sp = {a: v for a, v in st.items() if a not in ("pos", "fade", "fallback", "font")}
        if fam:
            sp["font"] = fam
        if "size" in sp:
            sp["size"] = round(sp["size"] * k, 1)
        s2 += [("captions.add", {"track": tr, "text": t, "seconds": max(0.0, a + off), "durationSeconds": max(0.05, b - a)})
               for a, b, t in cues]
        s2.append(("captions.setStyle", dict(sp, track=tr)))
    _, r2, _ = run_steps(proj, s2)
    lists = [r["result"] for r in r2 if r.get("id") == "graphics.list"]
    fx = []
    for (x, st, n), cid, L in zip(made, ids, lists):
        x0, y0, x1, y1 = L["layers"][0]["localBounds"]
        P = st.get("pos", "lower-left")
        if isinstance(P, list):
            P = {"x": P[0], "y": P[1], "h": "left", "v": "baseline"}
        elif P in POS:
            P = POS[P]
        else:
            sys.exit(f"no position '{P}' in titles.json")
        ax, ay = P["x"] * w / 1920, P["y"] * h / 1080
        trail = max(0, st.get("tracking", 0)) / 1000 * st["size"]     # tracking also pads after the last letter
        nl = x["text"].count("\n")
        cap, last = -y0 * 0.75, (y1 - y0) * nl / (nl + 1)              # cap height ~ 3/4 of the ascent; extra lines
        px = {"left": ax - x0, "right": ax - (x1 - trail), "center": ax - (x0 + x1 - trail) / 2}[P.get("h", "left")]
        py = {"baseline": ay - last, "top": ay + cap, "middle": ay + (cap - last) / 2}[P.get("v", "baseline")]
        fx.append(("graphics.set", {"clip": cid, "layer": 0, "props": {"position": [round(px, 1), round(py, 1)]}}))
        fd = st.get("fade", 0)
        fi, fo = (fd if isinstance(fd, list) else [fd, fd])[:2]
        for edge, f in (("in", fi), ("out", fo)):
            f = min(int(f), n // 2)
            if f > 0:
                fx.append(("sequence.applyVideoTransition", {"clip": cid, "edge": edge, "effect": "cross_dissolve", "frames": f}))
    cnt = (f" {len(made)} titles" if made else "") + (f" {sum(len(s[1]) for s in subs)} subs" if subs else "")
    return fx, cnt, "; ".join(notes)


def from_plan(cut):
    """A cut list written by song_cut.py is first rewritten from its <song>.plan.json, with every shot
    rendered so far (Comfort queues these builds while the rest of the shots still render)."""
    full = cut if os.path.exists(cut) else os.path.join(HERE, cut)
    try:
        first = open(full, encoding="utf-8").readline()
    except OSError:
        return
    if "built by song_cut.py" in first:
        import song_cut
        d, song = os.path.dirname(os.path.abspath(full)), os.path.splitext(os.path.basename(full))[0]
        print(song_cut.write(d, song, partial=True) + song_cut.copy_pictures(d, song))


def build(cut):
    t0 = time.time()
    from_plan(cut)
    p = parse(cut)
    out = to_local(p["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    proj = os.path.splitext(out)[0] + ".fcproj"
    seq = p["seq"]
    paths = [c["path"] for c in seq] + ([p["music"]["path"]] if p["music"] else [])
    missing = [x for x in paths if not os.path.exists(x)]
    if missing:
        sys.exit("missing: " + ", ".join(missing))
    ids = import_media(paths, proj)
    info = media_info(proj)
    first = info[ids[0]]
    w, h, fps = p["size"] or ((first["w"], first["h"], first["fps"]) if seq else (1920, 1080, 60.0))
    for c, item in zip(seq, ids):
        m = info[item]
        a, b = c["trim"] or (0, m["sec"])
        c.update(item=item, m=m, a=a, b=min(b, m["sec"]), pieces=None)
    report = ramp_plan(p, cut, fps)
    vt = title_tracks(p)
    # 1) place: ramped clips as video pieces at 100 % (their sound goes in later), others as one linked clip
    steps = [("file.newSequence", {"name": os.path.basename(os.path.splitext(out)[0]), "width": w, "height": h,
                                   "fps": round(fps, 3), "video": vt, "audio": 2})]
    t = 0.0
    for c in seq:
        f = c["m"]["fps"]
        if c["pieces"]:
            for s0, sn, tl, sp in c["pieces"]:
                steps.append(("timeline.place", {"item": c["item"], "track": "V1", "time": round(t * TICK),
                                                 "sourceIn": round((c["a"] + s0 / f) * TICK),
                                                 "duration": round(sn / f * TICK), "audio": False}))
                t += sn / f
        else:
            d = {"item": c["item"], "track": "V1", "time": round(t * TICK), "sourceIn": round(c["a"] * TICK), "duration": round((c["b"] - c["a"]) * TICK)}
            if not p.get("clipaudio", True):
                d["audio"] = False
            steps.append(("timeline.place", d))
            t += c["b"] - c["a"]
    if p["music"] and not seq:                    # song only: the whole song on A2 from its at= second
        mi = ids[len(seq)]
        steps.append(("timeline.place", {"item": mi, "track": "A2", "time": round(p["music"]["at"] * TICK),
                                         "sourceIn": 0, "duration": round(info[mi]["sec"] * TICK)}))
    code, outp, err = run_steps(proj, steps)
    res = iter(r["result"]["clips"] for r in outp[1:])
    for c in seq:
        if c["pieces"]:
            c["v"], c["au"] = [next(res)[0] for _ in c["pieces"]], None
        else:
            got = next(res)
            c["v"], c["au"] = [got[0]], (got[1] if len(got) > 1 else None)
    # 2) speed each piece (ripple keeps them back to back); frame blending smooths the in-betweens
    sp = [("clip.speedDuration", {"clips": [v], "speed": round(pc[3] * 100, 4), "ripple": True, "interpolation": "frameBlending"})
          for c in seq if c["pieces"] for v, pc in zip(c["v"], c["pieces"]) if abs(pc[3] - 1) > 0.004]
    if sp:
        run_steps(proj, sp)
    pos = clip_positions(proj)
    # 3) the ramped clips' own sound, under their pieces at normal speed
    au = []
    for c in seq:
        if c["pieces"] and c["m"]["audio"] and p.get("clipaudio", True):
            st = pos[c["v"][0]][0]
            en = pos[c["v"][-1]][0] + pos[c["v"][-1]][1]
            au.append((c, ("timeline.place", {"item": c["item"], "track": "A1", "time": st, "sourceIn": round(c["a"] * TICK),
                                              "duration": min(en - st, round((c["b"] - c["a"]) * TICK))})))
    if au:
        _, r3, _ = run_steps(proj, [s for _, s in au])
        for (c, _), r in zip(au, r3):
            c["au"] = r["result"]["clips"][0]
    mclip = None
    if p["music"] and seq:                        # the song on A2 under the edit, trimmed to where the edit ends
        mi = ids[len(seq)]
        st = round(p["music"]["at"] * TICK)
        end = max(pos[c["v"][-1]][0] + pos[c["v"][-1]][1] for c in seq)
        dur = round(info[mi]["sec"] * TICK) if p.get("musicfull") else min(round(info[mi]["sec"] * TICK), end - st)
        if dur > 0:
            _, r4, _ = run_steps(proj, [("timeline.place", {"item": mi, "track": "A2", "time": st, "sourceIn": 0, "duration": dur})])
            mclip = r4[0]["result"]["clips"][0]
    tfx, tcount, fnote = add_titles(proj, p, pos, w, h, fps)   # text + subs lines
    # 4) fit, transitions, fades
    fx, n_tr = [], 0
    if p["fit"] != "none":
        off = [v for c in seq if (c["m"]["w"], c["m"]["h"]) != (w, h) for v in c["v"]]
        if off:
            fx.append(("clip.fillFrame" if p["fit"] == "fill" else "clip.fitToFrame", {"clips": off}))
    for i, c in enumerate(seq):
        if "tr" in c and i + 1 < len(seq):
            eff, fr, prm, rev = c["tr"]
            d = {"clip": c["v"][-1], "edge": "out", "effect": eff, "frames": fr}
            if prm:
                d["params"] = prm
            if rev:
                d["reverse"] = True
            fx.append(("sequence.applyVideoTransition", d))
            if c["au"] is not None:
                fx.append(("sequence.applyAudioTransition", {"clip": c["au"], "edge": "out", "effect": "constant_power", "frames": fr}))
            n_tr += 1
    for key, c, v, edge in ((("fadein", seq[0], seq[0]["v"][0], "in"), ("fadeout", seq[-1], seq[-1]["v"][-1], "out")) if seq else ()):
        if p[key]:
            fx.append(("sequence.applyVideoTransition", {"clip": v, "edge": edge, "effect": "dip_to_black", "frames": p[key]}))
            if c["au"] is not None:
                fx.append(("sequence.applyAudioTransition", {"clip": c["au"], "edge": edge, "effect": "exponential_fade", "frames": p[key]}))
    if mclip is not None and p["fadeout"]:
        fx.append(("sequence.applyAudioTransition", {"clip": mclip, "edge": "out", "effect": "exponential_fade", "frames": p["fadeout"]}))
    fx += tfx
    if fx:
        run_steps(proj, fx)
    if not seq:                                   # song only, no clips yet: save the project, nothing to render
        winify(proj)
        print(f"ok project {os.path.relpath(proj, HERE)} | music {info[ids[0]]['sec']:.1f}s on A2, no clips yet (no render) | {time.time() - t0:.0f}s")
        return
    burn = ["--settings", json.dumps({"burnCaptions": True})] if p["subs"] else []
    code, o, err = fc("--project", proj, "export", out, *burn)
    if code:
        sys.exit("export failed: " + (err or o).strip()[-400:])
    winify(proj)
    ends = [(pos[c["v"][-1]][0] + pos[c["v"][-1]][1]) / TICK for c in seq]
    t = ends[-1]
    json.dump([round(e, 3) for e in ends[:-1]], open(os.path.splitext(out)[0] + ".cuts.json", "w"))
    with open(os.path.splitext(out)[0] + ".ramps.txt", "w", encoding="utf-8") as fh:
        fh.write("motion as rendered -> after the speed ramp (. still  - = + * # moving), speeds used, new length\n")
        fh.write("\n".join(report) + "\n")
    nr = sum(1 for c in seq if c["pieces"])
    print(f"ok {os.path.relpath(out, HERE)} {t:.1f}s {w}x{h}@{fps:.4g} {len(seq)} clips{' + music' if p['music'] else ''} {n_tr} transitions "
          f"{nr} ramped{tcount} | project {os.path.relpath(proj, HERE)} | {time.time() - t0:.0f}s" + (f" | fonts: {fnote}" if fnote else "")
          + "".join(f" | copied to {d}" for d in copy_out(out, p["copy"])))


def copy_out(out, dests):
    """copy lines: the finished video (and nothing else) to each place, e.g. the song's Preview folder."""
    import shutil
    done = []
    for d in dests:
        dst = to_local(d)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(out, dst + ".part")
        os.replace(dst + ".part", dst)
        done.append(d)
    return done


def run_steps(proj, steps):
    script = "\n".join(json.dumps({"id": i, "params": prm}) for i, prm in steps)
    r = subprocess.run([cli(), "--project", proj, "--save", "run", "-"], input=script, capture_output=True, text=True)
    res = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
    bad = [x for x in res if not x.get("ok")]
    if r.returncode or bad:
        x = bad[0] if bad else {}
        sys.exit(f"step failed: {x.get('id')} {x.get('error', r.stderr.strip()[:300])}")
    return r.returncode, res, r.stderr


def winify(proj):
    """Rewrite media paths so the project opens in FilmCraft on Windows."""
    if WIN:
        return
    d = json.load(open(proj, encoding="utf-8"))

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "path" and isinstance(v, str):
                    x[k] = to_win(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d["project"])
    json.dump(d, open(proj, "w", encoding="utf-8"), separators=(",", ":"))


# ---------- peek ----------
def peek(video, secs):
    video = to_local(video)
    if not secs:
        secs = [1.0]
        try:
            for c in json.load(open(os.path.splitext(video)[0] + ".cuts.json")):
                secs += [c - 0.25, c, c + 0.25]
        except OSError:
            pass
    sel = "+".join(f"lt(prev_pts*TB\\,{s:.3f})*gte(pts*TB\\,{s:.3f})" for s in secs)
    png = os.path.splitext(video)[0] + "_peek.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf",
                    f"select='{sel}',scale=-2:240,tile={len(secs)}x1", "-frames:v", "1", png], check=True)
    print(png)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    {"scan": lambda: scan(args), "build": lambda: build(args[0]),
     "peek": lambda: peek(args[0], [float(s) for s in args[1:]])}.get(cmd, lambda: sys.exit(__doc__))()
