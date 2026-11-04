import json, subprocess, sys
D = 0.5
out, clips = sys.argv[1], sys.argv[2:]
def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", p], capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)["format"]["duration"])
durs = [dur(c) for c in clips]
args = ["ffmpeg", "-y", "-v", "error"]
for c in clips: args += ["-i", c]
parts = []
for i in range(len(clips)):
    parts.append(f"[{i}:v]fps=24,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
    parts.append(f"[{i}:a]aresample=48000,asetpts=PTS-STARTPTS[a{i}]")
vprev, aprev, t = "v0", "a0", durs[0]
for i in range(1, len(clips)):
    off = t - D
    parts.append(f"[{vprev}][v{i}]xfade=transition=fade:duration={D}:offset={off:.4f}[vx{i}]")
    parts.append(f"[{aprev}][a{i}]acrossfade=d={D}:c1=tri:c2=tri[ax{i}]")
    vprev, aprev, t = f"vx{i}", f"ax{i}", off + durs[i]
parts.append(f"[{aprev}]loudnorm=I=-20:TP=-1.5:LRA=11,aresample=48000[aout]")
args += ["-filter_complex", ";".join(parts), "-map", f"[{vprev}]", "-map", "[aout]", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
subprocess.run(args, check=True)
print("done", round(dur(out), 3))
