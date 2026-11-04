#!/usr/bin/env python3
"""song_jobs.py - a song's shot list -> Comfort picture + shot jobs and the plan song_cut.py builds from.
Justice 2026-10-27. The shot list is projects/<song>/<song>.shots.txt; times come from the SongMap json.

  python song_jobs.py <song>           check: one summary line + warnings; writes <song>.plan.json and _jobs/
  python song_jobs.py <song> --queue   also puts the jobs into Comfort's inbox (each job once; queued.txt)
  python song_jobs.py <song> --queue --batch N   only batch N.  #prefix x = job-name start (default z), #inpoint s = where each H3 shot is used from

shots.txt:
  #key value   settings: songmap, music, videos, comfort, pics (job name stem), queue (one letter: order between
               songs inside a batch), kind, subject2, neg, sound, fadein, fadeout, end, copy (A:\\..\\x.mp4: a copy
               of every finished build there; several with |)
  style K | lora=file.safetensors:1.1 or none | style words | palette | trigger words | look (for the video prompt)
  batch N      the shots after this go into queue batch N (z<NN><letter>..: batch 1 of every song before batch 2)
  @ 91.44 name the next shot starts on the beat nearest this second (a section start from the SongMap sheet)
  LEN | SRC | TRANSITION | LABEL | PROMPT ; FRAMING | MOTION
    LEN  bars (1, 0.5, 2) | s2.68 seconds | * up to the next @ | - not on the timeline (a spare to reuse)
    SRC  style key = a new picture + shot | =label or =label+1.2 = reuse that shot (1.2 s later into it;
         the label's start is enough: =gl08 finds gl08_glass_curl)
         | K@folder/NN-1_x.png = a new shot from an existing picture in Comfort out (style K)
         | K>label = a new picture made by Krea 2 edit from that shot's picture (another angle of the same place)
         | run <name>:<slot> = a shot of an existing H3 run | clip <file>@<sec> = an existing clip in videos
New shots go 3 per "H3 Reference Video (Comfort)" run in order (a short last run gets a spare angle).
"""
import bisect, hashlib, json, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CONT = ", one continuous move with strong, clear motion for the whole five seconds, never slowing to a stop."


def main():
    song, queue = sys.argv[1], "--queue" in sys.argv
    bsel = sys.argv[sys.argv.index("--batch") + 1] if "--batch" in sys.argv else None
    import fc, song_cut
    pdir = os.path.join(HERE, "projects", song)
    _st = os.path.dirname(HERE)                  # the Star Trek folder (A:\Ai projects\Star Trek on Justice's PC)
    cfg = {"videos": os.path.join(_st, "Comfort", "out", "videos"), "comfort": os.path.join(_st, "Comfort"),
           "kind": "nature", "subject2": "nature only: no people appear anywhere.", "neg": "no people, no text, no watermark",
           "sound": "Wind, water and nature sounds that fit each shot.", "fadein": "24", "fadeout": "60", "queue": "a", "prefix": "z", "inpoint": "0.4"}
    styles, rows, warn = {}, [], []
    texts = {}                                   # text <label> "WORDS" a-b style=.. pos=..  -> fc.py text lines over that shot
    for no, raw in enumerate(open(os.path.join(pdir, song + ".shots.txt"), encoding="utf-8"), 1):
        ln = raw.strip()
        if not ln:
            continue
        m = re.match(r"#(\w+)\s+(.*)", ln)
        if m and m.group(1) in ("songmap", "music", "videos", "comfort", "pics", "queue", "kind", "subject2", "neg",
                                "sound", "fadein", "fadeout", "end", "title", "copy", "prefix", "inpoint", "build", "within", "tail", "musicfull"):
            cfg[m.group(1)] = m.group(2).strip()
        elif ln.startswith("#"):
            continue
        elif ln.startswith("style "):
            f = [x.strip() for x in ln[6:].split("|")]
            lora = f[1].split("=", 1)[1] if "=" in f[1] else f[1]
            styles[f[0]] = {"lora": None if lora == "none" else lora, "words": f[2], "pal": f[3], "trig": f[4], "look": f[5]}
        elif ln.startswith("text "):
            p = ln[5:].split(None, 1)
            texts.setdefault(p[0], []).append("text " + p[1])
        elif ln.startswith("batch "):
            rows.append(("batch", int(ln.split()[1]), no))
        elif ln.startswith("@"):
            p = ln[1:].split(None, 1)
            rows.append(("at", float(p[0]), no))
        else:
            f = [x.strip() for x in ln.split("|")]
            f += [""] * (6 - len(f))
            rows.append(("shot", f, no))

    sm = json.load(open(os.path.join(pdir, cfg["songmap"]), encoding="utf-8"))
    B, bpb, dur = sm["beats"], sm["beats_per_bar"], float(cfg.get("end") or sm["duration"])
    per = (B[-1] - B[0]) / (len(B) - 1)

    def pos(t):
        if t <= B[0]:
            return (t - B[0]) / per
        if t >= B[-1]:
            return len(B) - 1 + (t - B[-1]) / per
        i = bisect.bisect_right(B, t) - 1
        return i + (t - B[i]) / (B[i + 1] - B[i])

    def at(x):
        if x <= 0:
            return B[0] + x * per
        if x >= len(B) - 1:
            return B[-1] + (x - len(B) + 1) * per
        i = int(x)
        return B[i] + (x - i) * (B[i + 1] - B[i])

    def snap(t):
        if t <= 0.05:
            return 0.0
        return min(B, key=lambda b: abs(b - t)) if abs(min(B, key=lambda b: abs(b - t)) - t) < per * 0.6 else t

    shots, by, group, cur, batch = [], {}, [], None, 1
    news = {}                                    # batch -> new shots (timeline + spares) in order

    def close(T, no):
        if not group:
            return
        last = group[-1]
        if last["e"] is not None and abs(last["e"] - T) > per * 1.5:
            warn.append(f"line {no}: shots before it end at {last['e']:.2f}, moved to {T:.2f} ({(T - last['e']) / per:+.1f} beats)")
        if last["e"] is not None and T - last["t"] < 0.3:
            warn.append(f"line {no}: {last['label']} only {T - last['t']:.2f}s")
        last["e"] = T
        group.clear()

    for kind, v, no in rows:
        if kind == "batch":
            batch = v
            continue
        if kind == "at":
            T = snap(v)
            close(T, no)
            cur = T
            continue
        L, src, tr, label, prompt, motion = v[:6]
        if not label or label in by:
            sys.exit(f"line {no}: label missing or used twice: {label!r}")
        s = {"label": label, "tr": tr, "line": no}
        if src in styles or (src.split("@")[0] in styles and "@" in src) or (src.split(">")[0] in styles and ">" in src):
            s.update(new=True, style=src.split("@")[0].split(">")[0], prompt=prompt, motion=motion, batch=batch)
            if "@" in src:                       # an existing picture (path under Comfort out): no picture job
                s["pic"] = cfg["comfort"] + "\\out\\" + src.split("@", 1)[1].replace("/", "\\")
            elif ">" in src:                     # Krea 2 edit of another shot's picture: another angle of the same place
                s["master"] = src.split(">", 1)[1].strip()
            news.setdefault(batch, []).append(s)
        elif src.startswith("="):                 # NO REPEATS (Justice 2026-10-27, README rule 3)
            sys.exit(f"line {no}: {src} repeats a shot - not allowed. A moment that returns needs a NEW picture from "
                     f"another angle: K>{src[1:].split('+')[0]} with a different framing (e.g. from behind, looking up)")
            m = re.match(r"=(\w+)([+-][\d.]+)?$", src)
            if not m:
                sys.exit(f"line {no}: bad reuse {src}")
            s.update(ref=m.group(1), off=float(m.group(2) or 0))
        elif src.startswith("run "):
            r, sl = src[4:].strip().rsplit(":", 1)
            s.update(run=r, slot=int(sl), off=0.0)
        elif src.startswith("clip "):
            c, a = src[5:].strip().rsplit("@", 1)
            s.update(clip=c, a=float(a))
        else:
            sys.exit(f"line {no}: unknown source {src!r} (style keys: {' '.join(styles)})")
        by[label] = s
        if L == "-":
            continue
        if cur is None:
            sys.exit(f"line {no}: a shot before the first @")
        if group and group[-1]["e"] is None:
            sys.exit(f"line {no}: a '*' shot must be the last before an @")
        s["t"] = cur
        if L == "*":
            s["e"] = None
        else:
            s["e"] = cur + float(L[1:]) if L.startswith("s") else at(pos(cur) + float(L) * bpb)
            cur = s["e"]
        group.append(s)
        shots.append(s)
    close(dur, "end")

    # runs: 3 new shots per run, per batch, in order
    pics, pre = cfg["pics"], cfg["prefix"]
    jobs, runs, k = {}, [], 0
    for b in sorted(news):
        lst = news[b]
        pj = {True: [], False: []}               # lora pictures / plain pictures
        for s in lst:
            if s.get("pic") or s.get("master"):
                continue
            st = styles[s["style"]]
            grp = pj[bool(st["lora"])]
            grp.append(s)
            s["pjob"] = f"{pics}_{'p' if st['lora'] else 'q'}{b:02d}"
            s["pidx"] = len(grp)
            s["pic"] = f"{cfg['comfort']}\\out\\{s['pjob']}\\{s['pidx']:02d}-1_{s['label']}.png"
        for has, grp in pj.items():
            if not grp:
                continue
            out = [f"#name {grp[0]['pjob']}", "#size 1376x768", "#n 1", "#seed random", "#style none"]
            for s in grp:
                st = styles[s["style"]]
                subj, _, frame = s["prompt"].partition(";")
                body = ", ".join(x for x in [subj.strip(), st["words"], frame.strip(), st["pal"], cfg["neg"], st["trig"]] if x)
                tag = f"[label={s['label']} lora={st['lora']}]" if has else f"[label={s['label']}]"
                out.append(f"{tag} {body}")
            jobs[f"{pre}{b:02d}{cfg['queue']}0{'p' if has else 'q'}_{grp[0]['pjob']}.txt"] = "\n".join(out) + "\n"
        ej = []
        for s in lst:
            if not s.get("master"):
                continue
            m = by.get(s["master"]) or next((by[l] for l in by if l.startswith(s["master"] + "_")), None)
            if not m or not m.get("pic") or m.get("master"):
                sys.exit(f"line {s['line']}: edit master {s['master']} must be a new picture shot")
            s["eimg"] = (f"{m['pjob']}/{m['pidx']:02d}-1_{m['label']}.png" if m.get("pjob")
                         else m["pic"].split("\\out\\", 1)[1].replace("\\", "/"))
            ej.append(s)
            s["pjob"], s["pidx"] = f"{pics}_e{b:02d}", len(ej)
            s["pic"] = f"{cfg['comfort']}\\out\\{s['pjob']}\\{s['pidx']:02d}-1_{s['label']}.png"
        if ej:
            out = [f"#name {ej[0]['pjob']}", "#size 1376x768", "#n 1", "#seed random", "#style none"]
            for s in ej:
                st = styles[s["style"]]
                subj, _, frame = s["prompt"].partition(";")
                body = ", ".join(x for x in [f"the same place, the same light and the same art style as this picture, now {frame.strip() or 'from another angle'}: {subj.strip()}", st["words"], st["pal"], cfg["neg"], st["trig"]] if x)
                out.append(f"[label={s['label']} wf=edit image={s['eimg']}" + (f" lora={st['lora']}" if st["lora"] else "") + f"] {body}")
            jobs[f"{pre}{b:02d}{cfg['queue']}0x_{ej[0]['pjob']}.txt"] = "\n".join(out) + "\n"
        for i in range(0, len(lst), 3):
            chunk = lst[i:i + 3]
            while len(chunk) < 3:
                c0 = chunk[0]
                alt = dict(c0, label=c0["label"] + "_alt", motion="The camera arcs slowly around the scene from the other side while everything in it keeps moving")
                chunk.append(alt)
                by[alt["label"]] = alt
            k += 1
            name = f"{pics}_r{k:02d}"
            for sl, s in enumerate(chunk):
                s["run"], s["slot"], s["off"] = name, sl, 0.0
            runs.append(name)
            jobs[f"{pre}{b:02d}{cfg['queue']}1_{name}.json"] = json.dumps(run_job(name, chunk, styles, cfg))
        if cfg.get("build") != "overseer":       # #build overseer: the Overseer builds once a batch is checked
            jobs[f"{pre}{b:02d}{cfg['queue']}2_fc_{song}_b{b:02d}.json"] = json.dumps({"filmcraft_build": f"projects/{song}/{song}.txt", "name": f"fc_{song}_b{b:02d}"})

    plan = {"title": cfg.get("title", song), "out": f"projects/{song}/{song}.mp4", "music": cfg["music"], "videos": cfg["videos"],
            "fadein": int(cfg["fadein"]), "fadeout": int(cfg["fadeout"]), "shots": [],
            "copy": [c.strip() for c in cfg.get("copy", "").split("|") if c.strip()],
            "pic_dirs": sorted({cfg["comfort"] + "\\out\\" + s["pjob"] for v in news.values() for s in v if s.get("pjob")})}
    plan["inpoint"] = float(cfg["inpoint"])
    plan["tail"] = float(cfg.get("tail", 4.98))
    plan["musicfull"] = cfg.get("musicfull", "on").strip().lower() not in ("off", "no", "0", "false")   # off: the song ends with the edit (fadeout)
    plan["within"] = [x.strip() for x in cfg.get("within", "").split("|") if x.strip()]
    if plan["copy"]:                             # the new pictures also go to Preview\<song>\full pictures (at each build)
        import ntpath
        plan["pic_copy"] = ntpath.join(ntpath.dirname(plan["copy"][0]), "full pictures")
    for s in shots:
        r = s
        if "ref" in s:
            hit = [l for l in by if l == s["ref"]] or [l for l in by if l.startswith(s["ref"] + "_") and not l.endswith("_alt") and "ref" not in by[l]]
            if len(hit) != 1:
                sys.exit(f"line {s['line']}: reuse {s['ref']} matches {hit or 'nothing'}")
            r = by[hit[0]]
        if "ref" in s and "ref" in r:
            sys.exit(f"line {s['line']}: reuse of a reuse ({s['ref']})")
        e = {"t": round(s["t"], 3), "e": round(s["e"], 3), "label": s["label"]}
        if s["tr"]:
            e["tr"] = s["tr"]
        tx = [t for k, v in texts.items() if s["label"] == k or s["label"].startswith(k + "_") for t in v]
        if tx:
            e["text"] = tx
        if "clip" in r:
            e.update(clip=r["clip"], a=round(r["a"] + s.get("off", 0), 3))
        else:
            e.update(run=r["run"], slot=r["slot"], off=round(r.get("off", 0) + (s.get("off", 0) if "ref" in s else 0), 3))
        if "run" in e and e["e"] - e["t"] > (4.98 - plan['inpoint']):
            warn.append(f"line {s['line']}: {s['label']} {e['e'] - e['t']:.2f}s is longer than its shot: slowed to {100 * (4.98 - plan['inpoint']) / (e['e'] - e['t']):.0f}%")
        plan["shots"].append(e)
    json.dump(plan, open(os.path.join(pdir, song + ".plan.json"), "w", encoding="utf-8"), indent=0)

    jd = os.path.join(pdir, "_jobs")
    os.makedirs(jd, exist_ok=True)
    for n, body in jobs.items():
        open(os.path.join(jd, n), "w", encoding="utf-8", newline="\n").write(body)
    queued = {}
    qf = os.path.join(jd, "queued.txt")
    if os.path.exists(qf):
        for l in open(qf, encoding="utf-8"):
            n, h = l.split()
            queued[n] = h
    nq = 0
    if queue:
        inbox = fc.to_local(cfg["comfort"] + "\\inbox")
        for n, body in sorted(jobs.items()):
            if bsel and not n.startswith(f"{pre}{int(bsel):02d}"):
                continue
            h = hashlib.md5(body.encode()).hexdigest()[:10]
            if n in queued:
                if queued[n] != h:
                    warn.append(f"{n} changed after it was queued (not re-queued)")
                continue
            tmp = os.path.join(inbox, ".t")
            open(tmp, "w", encoding="utf-8", newline="\n").write(body)
            os.replace(tmp, os.path.join(inbox, n))
            queued[n] = h
            nq += 1
        open(qf, "w", encoding="utf-8").write("".join(f"{n} {h}\n" for n, h in sorted(queued.items())))
    cut = song_cut.write(pdir, song, partial=True)
    tl = [s["e"] - s["t"] for s in shots]
    newp = sum(len(v) for v in news.values())
    print(f"{song}: {len(shots)} shots 0-{shots[-1]['e']:.2f}s, ASL {sum(tl) / len(tl):.2f}s (min {min(tl):.2f}, max {max(tl):.2f}), "
          f"{newp} new pictures, {len(runs)} runs (~{len(runs) * 6.6 / 60:.1f} h), {sum(1 for s in shots if 'ref' in s)} reused"
          + (f", {nq} jobs queued" if queue else f", {len(jobs)} jobs ready") + f" | {cut}")
    for w in warn:
        print("  ! " + w)


def run_job(name, chunk, styles, cfg):
    looks = [styles[s["style"]]["look"] for s in chunk]
    same = len(set(looks)) == 1
    s1 = (f"<Subject 1> is the rendering style of <Picture 1>, <Picture 2> and <Picture 3>: {looks[0]}." if same else
          "<Subject 1> is the rendering style of each picture: every shot keeps the look of its own first frame ("
          + "; ".join(f"<Picture {i + 1}>: {l}" for i, l in enumerate(looks)) + ").")
    pics = []
    for i, s in enumerate(chunk):
        subj, _, frame = s["prompt"].partition(";")
        pics.append(f"<Picture {i + 1}> is the first frame of [Shot {i + 1}], showing {subj.strip()}" + (f"; {frame.strip()}." if frame.strip() else "."))
    det = []
    for i, s in enumerate(chunk):
        mv = s["motion"].rstrip(". ") + CONT
        det.append(f"[Shot 1] The shot begins from <Picture 1>. {mv}" if i == 0 else f"[Shot {i + 1}] At 00:{5 * i:02d}.000, the camera cuts to <Picture {i + 1}>. {mv}")
    kind = cfg["kind"]
    p = ("subject_definitions:\n" + s1 + "\n<Subject 2> is " + cfg["subject2"] + "\n" + "\n".join(pics) + "\n\nsummary:\n"
         f"[keyframe completion + reference generation] A 15-second 16:9 sequence of three separate {kind} shots of five seconds each "
         "with hard cuts at 00:05 and 00:10, in <Subject 1>.\n\nretention_analysis:\n"
         + ("<Subject 1> (applies to every shot): fully_preserved - the same painted look in every frame; never photographic.\n" if same else
            "<Subject 1> (applies to every shot): fully_preserved - each shot keeps the painted look of its own first frame; never photographic.\n")
         + "<Subject 2>: fully_preserved.\n"
         + "".join(f"<Picture {i + 1}> ([Shot {i + 1}] first frame): fully_preserved - its composition, lighting and positions.\n" for i in range(3))
         + f"\ndetailed_description:\nThe target video is three separate music-video shots in <Subject 1>, everything alive and moving.\n"
         + "\n".join(det) + "\n\noverall_soundscape:\n" + cfg["sound"] + "\n\nnon_diegetic_music:\nN/A")
    return {"workflow": "H3 Reference Video (Comfort)", "name": name, "set": {"ref.prompt": p, "ref.length": 362},
            "images": {f"pic{i + 1}.image": s["pic"] for i, s in enumerate(chunk)}, "seed": "random"}


if __name__ == "__main__":
    main()
