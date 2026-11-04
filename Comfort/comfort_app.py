"""Comfort app server: UI + local master AI + any-workflow runner + inbox watcher, on http://127.0.0.1:8790.
Started by Comfort.exe (pythonw, no console). Uses only packages already in the ClaudeComfy venv (aiohttp, Pillow)."""
import json, os, re, socket, subprocess, sys, threading, time, traceback, uuid

from aiohttp import web

import comfort as C
import comfort_flows as F
import comfort_agent as A

AGENT = A.Agent()
CODE_FILES = ["comfort.py", "comfort_app.py", "comfort_agent.py", "comfort_flows.py"]
VERSION = max(os.path.getmtime(C.P(f)) for f in CODE_FILES)   # Comfort.exe restarts the app when files on disk are newer
TASK = {"busy": None, "last": None}
SETTING_KEYS = {"comfy_url", "free_after_job", "default_upscale_model"}
LLM_KEYS = {"url", "model", "keep_alive", "vram_handoff", "num_ctx", "show_results", "max_steps", "think"}


def background(label, fn, *args):
    if TASK["busy"]:
        raise web.HTTPConflict(text="busy with: " + TASK["busy"])
    def run():
        TASK["busy"] = label
        try:
            TASK["last"] = {"label": label, "ok": True, "result": fn(*args), "t": time.time()}
        except Exception as e:
            C.log("%s failed: %s" % (label, traceback.format_exc()))
            TASK["last"] = {"label": label, "ok": False, "error": str(e), "t": time.time()}
        finally:
            TASK["busy"] = None
    threading.Thread(target=run, daemon=True).start()


CODE = ["comfort.py", "comfort_app.py", "comfort_agent.py", "comfort_flows.py"]

def restart_self():
    C.log("code changed - restarting Comfort app")
    subprocess.Popen([sys.executable, "-s", os.path.abspath(__file__)], cwd=C.ROOT,
                     creationflags=0x08000000 if os.name == "nt" else 0)
    os._exit(0)

def watcher():
    beat = 0
    stamps = {f: os.path.getmtime(C.P(f)) for f in CODE}
    while True:
        try:
            if any(os.path.getmtime(C.P(f)) != t for f, t in stamps.items()) and not AGENT.busy and not TASK["busy"]:
                if C.JOB_LOCK.acquire(blocking=False):
                    restart_self()
            if C.process_inbox_once("app"):
                continue
            if time.time() - beat > 10:
                if C.JOB_LOCK.acquire(blocking=False):
                    try:
                        C.set_status("idle (Comfort app)")
                    finally:
                        C.JOB_LOCK.release()
                beat = time.time()
        except Exception as e:
            C.log("watcher: %s" % e)
        time.sleep(1)


def safe_join(base, tail):
    p = os.path.abspath(os.path.join(base, tail))
    if not p.startswith(os.path.abspath(base) + os.sep):
        raise web.HTTPForbidden()
    if not os.path.isfile(p):
        raise web.HTTPNotFound()
    return p


def jjson(data):
    return web.json_response(data, dumps=lambda o: json.dumps(o, default=str))


# ------------------------------------------------------------------ routes
routes = web.RouteTableDef()

@routes.get("/")
async def index(_):
    return web.FileResponse(C.P("ui.html"), headers={"Cache-Control": "no-store"})

@routes.get("/out/{tail:.*}")
async def out_file(req):
    return web.FileResponse(safe_join(C.P("out"), req.match_info["tail"]))

@routes.get("/inputs/{tail:.*}")
async def in_file(req):
    return web.FileResponse(safe_join(C.P("inputs"), req.match_info["tail"]))

ST_OV = os.path.normpath(C.P("..", "Overseer"))

def _st_songs():
    out = []
    try:
        for ln in open(os.path.join(ST_OV, "songs.txt"), encoding="utf-8"):
            p = ln.split("#")[0].split()
            if p:
                out.append((p[0], p[1] if len(p) > 1 else "auto"))
    except OSError:
        pass
    return out

def _st_preview(song):
    try:
        for ln in open(os.path.normpath(C.P("..", "FilmCraft", "projects", song, song + ".shots.txt")), encoding="utf-8"):
            if ln.startswith("#copy "):
                return ln[6:].strip().split("|")[0].strip()
    except OSError:
        pass
    return ""

@routes.get("/startrek")
async def startrek_page(_):
    return web.FileResponse(os.path.join(ST_OV, "startrek.html"), headers={"Cache-Control": "no-store"})

@routes.get("/api/startrek")
async def startrek_state(_):
    songs = []
    for name, mode in _st_songs():
        rd = lambda p: open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        lg = rd(os.path.join(ST_OV, "logs", name + ".log")).splitlines()[-80:]
        pv = _st_preview(name)
        songs.append({"name": name, "mode": mode, "report": rd(os.path.join(ST_OV, "report_%s.txt" % name)), "log": lg[::-1],
                      "preview": pv, "preview_mtime": os.path.getmtime(pv) if pv and os.path.exists(pv) else 0})
    st = open(C.P("status.txt"), encoding="utf-8").read().strip() if os.path.exists(C.P("status.txt")) else ""
    inbox = [f for f in os.listdir(C.P("inbox")) if f.lower().endswith((".txt", ".json")) and not f.startswith(("_", "."))]
    return jjson({"songs": songs, "paused": os.path.exists(os.path.join(ST_OV, "PAUSE")), "status": st, "queue": sorted(inbox)[:12],
                  "queued": len(inbox), "agent_busy": AGENT.busy})

@routes.post("/api/startrek/cmd")
async def startrek_cmd(req):
    d = await req.json()
    act = str(d.get("action", ""))
    if act not in ("pause", "resume", "mode", "redo", "rebuild", "review", "status"):
        raise web.HTTPBadRequest(text="unknown action")
    args = [act] + [str(x) for x in (d.get("song"), d.get("arg")) if x]
    exe = sys.executable[:-5] + ".exe" if sys.executable.lower().endswith("pythonw.exe") else sys.executable
    import asyncio
    r = await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(
        [exe, os.path.join(ST_OV, "overseer.py")] + args, capture_output=True, text=True, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
    return jjson({"out": ((r.stdout or "") + (r.stderr or "")).strip()[-6000:]})

@routes.get("/api/startrek/video")
async def startrek_video(req):
    pv = _st_preview(req.query.get("song", ""))
    if not pv or not os.path.exists(pv):
        raise web.HTTPNotFound()
    return web.FileResponse(pv)

@routes.get("/api/startrek/sheet")
async def startrek_sheet(req):
    f = os.path.basename(req.query.get("f", ""))
    p = os.path.join(ST_OV, "sheets", f)
    if not f.endswith(".jpg") or not os.path.exists(p):
        raise web.HTTPNotFound()
    return web.FileResponse(p)

@routes.get("/api/state")
async def state(_):
    s, _age = (open(C.P("status.txt"), encoding="utf-8").read().strip() if os.path.exists(C.P("status.txt")) else "", 0)
    return jjson({"version": VERSION, "ollama_installed": bool(A.find_ollama()), "status": s, "comfy": C.comfy_up(), "llm": A.status(), "llm_cfg": A.cfg(),
                  "agent": {"busy": AGENT.busy, "status": AGENT.status, "count": len(AGENT.display)},
                  "task": {"busy": TASK["busy"], "last": TASK["last"]}, "workflows": len(F.list_workflows())})

@routes.get("/api/agent/log")
async def agent_log(req):
    since = int(req.query.get("since", 0))
    return jjson({"items": AGENT.display[since:], "busy": AGENT.busy, "status": AGENT.status})

@routes.post("/api/agent/send")
async def agent_send(req):
    d = await req.json()
    if not (d.get("text") or "").strip():
        raise web.HTTPBadRequest(text="empty message")
    try:
        AGENT.send(d["text"].strip(), d.get("attachments") or [])
    except RuntimeError as e:
        raise web.HTTPConflict(text=str(e))
    return jjson({"ok": True})

@routes.post("/api/agent/stop")
async def agent_stop(_):
    AGENT.stop = True
    return jjson({"ok": True})

@routes.post("/api/agent/reset")
async def agent_reset(_):
    if AGENT.busy:
        raise web.HTTPConflict(text="busy")
    AGENT.reset()
    return jjson({"ok": True})

@routes.post("/api/upload")
async def upload(req):
    reader = await req.multipart()
    names = []
    while True:
        part = await reader.next()
        if part is None:
            break
        if not part.filename:
            continue
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(part.filename)) or "image.png"
        name = base
        while os.path.exists(C.P("inputs", name)):
            stem, ext = os.path.splitext(base)
            name = "%s_%s%s" % (stem, uuid.uuid4().hex[:4], ext)
        with open(C.P("inputs", name), "wb") as f:
            while True:
                chunk = await part.read_chunk()
                if not chunk:
                    break
                f.write(chunk)
        names.append(name)
    return jjson({"names": names})

@routes.get("/api/workflows")
async def workflows(_):
    ready = F.list_workflows()
    return jjson({"workflows": ready, "not_converted": [u for u in F.ui_workflows() if u not in ready and u not in A.REPLACED]})

@routes.get("/api/workflow")
async def workflow(req):
    try:
        name, g = F.load_workflow(req.query["name"])
    except Exception as e:
        raise web.HTTPNotFound(text=str(e))
    nodes = [{"id": nid, "class": ct, "title": title, "params": params} for nid, ct, title, params in F.nodes_with_params(g)]
    return jjson({"name": name, "nodes": nodes, "guide": F.guide(name)})

@routes.post("/api/workflow/run")
async def workflow_run(req):
    d = await req.json()
    spec = {"workflow": d["workflow"], "set": d.get("set") or {}, "images": d.get("images") or {},
            "n": int(d.get("n") or 1), "seed": d.get("seed") or "random", "name": d.get("name")}
    background("run " + d["workflow"], lambda: os.path.basename(F.run_flow(spec)[0]))
    return jjson({"ok": True})

@routes.post("/api/convert")
async def convert(req):
    d = await req.json() if req.can_read_body else {}
    background("convert workflows", F.convert_workflows, d.get("only"))
    return jjson({"ok": True})

@routes.post("/api/upscale")
async def upscale(req):
    d = await req.json()
    background("upscale " + d["image"], lambda: os.path.basename(F.upscale_image(d["image"], d["size"])[0]))
    return jjson({"ok": True})

@routes.post("/api/llm/benchmark")
async def llm_benchmark(_):
    background("AI speed test", A.benchmark)
    return jjson({"ok": True})

@routes.post("/api/comfy/start")
async def comfy_start(_):
    background("start ComfyUI", C.ensure_comfy)
    return jjson({"ok": True})

@routes.get("/api/jobs")
async def jobs(req):
    limit = int(req.query.get("limit", 20))
    d = C.P("out")
    names = sorted((j for j in os.listdir(d) if os.path.isdir(os.path.join(d, j))), key=lambda j: os.path.getmtime(os.path.join(d, j)), reverse=True)[:limit]
    out = []
    for j in names:
        p = os.path.join(d, j)
        head = ""
        if os.path.exists(os.path.join(p, "_done.txt")):
            with open(os.path.join(p, "_done.txt"), encoding="utf-8") as f:
                head = f.readline().strip()
        files = sorted(f for f in os.listdir(p) if not f.startswith("_") and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".gif")))
        out.append({"name": j, "t": os.path.getmtime(p), "head": head, "sheet": os.path.exists(os.path.join(p, "_sheet.jpg")), "files": files})
    return jjson({"jobs": out})

VID_EXTS = (".mp4", ".webm", ".mov", ".mkv")

@routes.get("/api/videos")
async def videos(req):
    """Every video Comfort made: out\videos\*.mp4 (info in out\video_info\<name>\) plus older videos inside job folders."""
    d = C.P("out"); out = []
    vd = os.path.join(d, "videos")
    if os.path.isdir(vd):
        for f in os.listdir(vd):
            if f.lower().endswith(VID_EXTS):
                stem = os.path.splitext(f)[0]; head = ""
                dn = os.path.join(d, "video_info", stem, "_done.txt")
                if os.path.exists(dn):
                    with open(dn, encoding="utf-8") as fh:
                        head = fh.readline().strip()
                out.append({"name": stem, "path": "videos/" + f, "t": os.path.getmtime(os.path.join(vd, f)), "head": head})
    for j in os.listdir(d):
        p = os.path.join(d, j)
        if j in ("videos", "video_info") or not os.path.isdir(p):
            continue
        for f in os.listdir(p):
            if f.lower().endswith(VID_EXTS) and not f.startswith("_"):
                out.append({"name": j + "/" + f, "path": j + "/" + f, "t": os.path.getmtime(os.path.join(p, f)), "head": ""})
    out.sort(key=lambda v: v["t"], reverse=True)
    return jjson({"videos": out[:int(req.query.get("limit", 20))]})

@routes.get("/api/videoinfo")
async def videoinfo(req):
    name = req.query["name"]
    p = os.path.join(C.P("out"), os.path.basename(name.split("/")[0])) if "/" in name else os.path.join(C.P("out"), "video_info", os.path.basename(name))
    info = {}
    for fn in ("_done.txt", "_texts.txt", "_prompts.txt"):
        if os.path.exists(os.path.join(p, fn)):
            with open(os.path.join(p, fn), encoding="utf-8") as f:
                info[fn] = f.read()[:8000]
    mf = os.path.join(p, "_manifest.json")
    if os.path.exists(mf):
        try:
            with open(mf, encoding="utf-8") as f:
                m = json.load(f)
            if m.get("workflow"):
                info["workflow"] = m["workflow"]
            pics = "\n".join(str(v) for v in (m.get("images") or {}).values())
            if pics:
                info["pictures"] = pics
            pr = (m.get("set") or {}).get("ref.prompt")
            if pr:
                info["prompt"] = pr[:8000]
        except Exception:
            pass
    return jjson(info)

@routes.get("/api/job")
async def job(req):
    p = os.path.join(C.P("out"), os.path.basename(req.query["name"]))
    info = {}
    for fn in ("_done.txt", "_prompts.txt", "_texts.txt"):
        if os.path.exists(os.path.join(p, fn)):
            with open(os.path.join(p, fn), encoding="utf-8") as f:
                info[fn] = f.read()[:8000]
    return jjson(info)

@routes.get("/api/settings")
async def get_settings(_):
    return jjson({"llm": A.cfg(), **{k: C.CFG.get(k) for k in SETTING_KEYS}})

@routes.post("/api/settings")
async def post_settings(req):
    d = await req.json()
    path = os.environ.get("COMFORT_CONFIG", C.P("config.json"))
    cfg = C.load_json(path)
    for k in SETTING_KEYS:
        if k in d:
            cfg[k] = d[k]
    llm = cfg.setdefault("llm", {})
    for k, v in (d.get("llm") or {}).items():
        if k in LLM_KEYS:
            llm[k] = v
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    os.replace(path + ".tmp", path)
    C.reload_data()
    C.URL = C.CFG["comfy_url"].rstrip("/")
    return jjson({"ok": True})

@routes.post("/api/quit")
async def quit_app(_):
    def bye():
        time.sleep(0.5)
        A.unload()
        os._exit(0)
    threading.Thread(target=bye, daemon=True).start()
    return jjson({"ok": True})


def cancel_comfy(why="button"):
    """Stop the job ComfyUI is running now (interrupt) and drop anything queued behind it in ComfyUI."""
    import urllib.request
    done = []
    for path, body in (("/interrupt", b"{}"), ("/queue", b'{"clear": true}')):
        try:
            req = urllib.request.Request(C.URL + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=10).read()
            done.append(path)
        except Exception as e:
            C.log("cancel %s failed: %s" % (path, e))
    C.log("CANCEL requested (%s): sent %s" % (why, ", ".join(done) or "nothing"))
    return done

@routes.post("/api/cancel")
async def api_cancel(req):
    return jjson({"ok": True, "sent": cancel_comfy("button")})

def cancel_watch():
    """Claude (or anyone) can cancel from outside: create an empty file inbox\_CANCEL."""
    f = C.P("inbox", "_CANCEL")
    while True:
        try:
            if os.path.exists(f):
                os.remove(f)
                cancel_comfy("inbox\\_CANCEL")
        except Exception as e:
            C.log("cancel watch: %s" % e)
        time.sleep(2)

def heartbeat():
    """Justice 2026-10-27: proof of life. heartbeat.txt is rewritten every 5 s while Comfort runs (time | pid | status).
    Comfort is generating ONLY while this file is fresh (Star Trek README rule 8); Comfort Watchdog.vbs restarts
    Comfort.exe when it goes stale (unless Overseer\\PAUSE exists)."""
    while True:
        try:
            try:
                st = open(C.P("status.txt"), encoding="utf-8").read().strip().splitlines()[0]
            except Exception:
                st = ""
            with open(C.P("heartbeat.txt"), "w", encoding="utf-8") as f:
                f.write("%d|%s|pid %d|%s\n" % (time.time(), time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), st))
        except Exception:
            pass
        time.sleep(5)


def main():
    for d in ("inbox", "out", "inputs", os.path.join("jobs", "done"), os.path.join("jobs", "failed")):
        os.makedirs(C.P(d), exist_ok=True)
    if sys.stdout is None or sys.stderr is None:          # pythonw: no console
        sys.stdout = sys.stderr = open(C.P("app.log"), "a", encoding="utf-8", buffering=1)
    try:
        F.ensure_builtin_workflows()
    except Exception as e:
        C.log("builtin workflows: %s" % e)
    threading.Thread(target=heartbeat, daemon=True).start()
    if os.name == "nt" and os.path.exists(C.P("Comfort Watchdog.vbs")):   # Justice 2026-10-27: Comfort starts its own watchdog
        try:                                    # (it quits if one is already running; first run adds it to the Startup folder)
            subprocess.Popen(["wscript.exe", C.P("Comfort Watchdog.vbs")], cwd=C.ROOT, creationflags=0x08000000)
        except Exception as e:
            C.log("watchdog start: %s" % e)
    threading.Thread(target=watcher, daemon=True).start()
    threading.Thread(target=cancel_watch, daemon=True).start()
    def warm_up():                      # one click on Comfort.exe = everything ready
        try:
            A.ensure_ollama()
        except Exception as e:
            C.log("ollama start: %s" % e)
        if C.CFG.get("prestart_comfy", True):
            try:
                C.ensure_comfy()
            except Exception as e:
                C.log("comfy start: %s" % e)
    threading.Thread(target=warm_up, daemon=True).start()
    app = web.Application(client_max_size=200 * 1024 ** 2)
    app.add_routes(routes)
    port = int(C.CFG.get("app_port", 8790))
    for _ in range(60):                     # after a self-restart, wait for the old process to free the port
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            break
        except OSError:
            s.close()
            time.sleep(0.5)
    C.log("Comfort app on http://127.0.0.1:%d" % port)
    web.run_app(app, host="127.0.0.1", port=port, print=None, handle_signals=False)


if __name__ == "__main__":
    main()
