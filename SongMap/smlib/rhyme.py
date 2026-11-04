"""Approximate rhyme families for lyric lines: end rhymes (letter per line, kept across the song)
and internal rhymes. English from the CMU dictionary, Spanish by its stress rules, Patois through a
respelling map, anything else through a small letter-to-sound guess."""
from __future__ import annotations

import re
import unicodedata

try:
    import pronouncing
except Exception:  # noqa: BLE001
    pronouncing = None

FILLER = {"yeah", "yea", "ye", "oh", "ooh", "uh", "ah", "aah", "hey", "ya", "yo", "mmm", "mm", "hmm", "whoa",
          "woah", "na", "nah", "la", "eh", "huh", "woo", "uhh", "ohh", "ay", "ey", "oi", "ee"}
STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "it", "is", "i", "me", "my", "you", "your",
        "we", "he", "she", "they", "them", "dem", "mi", "yuh", "di", "de", "seh", "fi", "inna", "pon", "but", "so",
        "for", "with", "be", "am", "are", "was", "that", "this", "if", "as", "by", "do", "no", "not", "up", "all",
        "que", "el", "la", "lo", "los", "las", "un", "una", "y", "en", "es", "se", "con", "por", "para", "mi", "tu",
        "su", "al", "del", "me", "te", "le", "ya", "si", "ni", "o", "pero", "como"}
ES_HINT = {"que", "el", "los", "las", "una", "y", "en", "es", "se", "con", "por", "para", "tu", "su", "del",
           "pero", "como", "yo", "mi", "te", "lo", "la", "no", "muy", "más", "mas", "vida", "amor", "corazón"}
PATOIS = {"ting": "thing", "tings": "things", "dem": "them", "dat": "that", "dis": "this", "di": "the",
          "fi": "fee", "mi": "me", "yuh": "you", "unu": "you", "seh": "say", "nuh": "no", "cyaan": "can't",
          "caan": "can't", "wah": "what", "bwoy": "boy", "gyal": "gal", "pickney": "picky", "fiya": "fire",
          "bredda": "brother", "breda": "brother", "sistren": "sister", "bredren": "brethren", "likkle": "little",
          "nuff": "enough", "pon": "on", "inna": "in", "deh": "there", "yah": "here", "ya": "here", "suh": "so",
          "jah": "jaw", "irie": "eerie", "babylon": "babylon", "rasta": "raster", "zion": "zion", "riddim": "rhythm",
          "dutty": "dirty", "bun": "burn", "chant": "chant", "ital": "vital", "yute": "youth", "yout": "youth",
          "tek": "take", "mek": "make", "gwaan": "gone", "gwan": "gone", "nyam": "yam", "haffi": "have",
          "wid": "with", "widout": "without", "everyting": "everything", "nutten": "nothing", "notten": "nothing",
          "sumting": "something", "anyting": "anything", "ova": "over", "neva": "never", "eva": "ever",
          "betta": "better", "wata": "water", "mada": "mother", "fada": "father", "lova": "lover"}
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
SLANT = {"AO": "AA"}


def _plain(w: str) -> str:
    return re.sub(r"[^a-z']", "", w.lower()).strip("'")


def _strip(w: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- English ---
def _cmu(w: str) -> list[str] | None:
    if pronouncing is None or not w:
        return None
    p = pronouncing.phones_for_word(w)
    return p[0].split() if p else None


def _tail(ph: list[str]) -> tuple[str, str, int]:
    vi = [i for i, p in enumerate(ph) if p[-1].isdigit()]
    if not vi:
        return " ".join(ph), "", 0
    st = [i for i in vi if p_stress(ph[i]) in "12"] or vi
    i = st[-1]
    tail = [re.sub(r"\d", "", p) for p in ph[i:]]
    vow = [SLANT.get(p, p) for p in tail if p in VOWELS]
    return " ".join(tail), " ".join(vow), len(vow)


def p_stress(p: str) -> str:
    return p[-1] if p[-1].isdigit() else ""


# letter-to-sound for the last syllable of words no dictionary knows
_LTS = [("igh", "AY"), ("eigh", "EY"), ("ough", "AO"), ("augh", "AO"), ("ee", "IY"), ("ea", "IY"), ("ie", "AY"),
        ("ai", "EY"), ("ay", "EY"), ("ey", "EY"), ("oo", "UW"), ("ou", "AW"), ("ow", "OW"), ("oi", "OY"),
        ("oy", "OY"), ("oa", "OW"), ("ue", "UW"), ("ew", "UW"), ("au", "AO"), ("aw", "AO"),
        ("a", "AE"), ("e", "EH"), ("i", "IH"), ("o", "AA"), ("u", "AH"), ("y", "IY")]
_LONG = {"a": "EY", "e": "IY", "i": "AY", "o": "OW", "u": "UW"}


def _guess(w: str) -> tuple[str, str, int]:
    w = re.sub(r"(.)\1+", r"\1", w)
    m = re.search(r"([aeiouy]+)([^aeiouy]*)$", w)
    if not m:
        return w, "", 0
    v, coda = m.group(1), m.group(2)
    pre = w[:m.start()]
    if v == "e" and not coda and pre:                       # silent final e: "time" -> AY M
        m2 = re.search(r"([aeiou])([^aeiouy]+)e$", w)
        if m2:
            return _LONG[m2.group(1)] + " " + m2.group(2).upper(), SLANT.get(_LONG[m2.group(1)], _LONG[m2.group(1)]), 1
    if v == "a" and not coda:                                # Patois "-a" ~ "-er" ending
        return "ER", "ER", 1
    sound = next((s for k, s in _LTS if v.endswith(k) or v == k), "AH")
    return f"{sound} {coda.upper()}".strip(), SLANT.get(sound, sound), 1


# ---------------------------------------------------------------- Spanish ---
_ES_STRONG = "aeoáéó"
_ES_V = "aeiouáéíóúü"


def _es(w: str) -> tuple[str, str, int] | None:
    w = re.sub(r"[^a-záéíóúüñ]", "", w.lower())
    if not w or not any(c in _ES_V for c in w):
        return None
    w = re.sub(r"^h", "", w).replace("qu", "k").replace("gue", "ge").replace("gui", "gi")
    nuclei = []                                          # (start, end) of each vowel nucleus
    i = 0
    while i < len(w):
        if w[i] in _ES_V:
            j = i + 1
            while j < len(w) and w[j] in _ES_V and not (w[j - 1] in _ES_STRONG and w[j] in _ES_STRONG) \
                    and w[j] not in "íú" and w[j - 1] not in "íú":
                j += 1
            nuclei.append((i, j))
            i = j
        else:
            i += 1
    acc = [k for k, (a, b) in enumerate(nuclei) if any(c in "áéíóú" for c in w[a:b])]
    if acc:
        k = acc[-1]
    elif w[-1] in "aeiouns":
        k = max(0, len(nuclei) - 2)
    else:
        k = len(nuclei) - 1
    a, b = nuclei[k]
    nuc = w[a:b]
    sv = next((c for c in nuc if c in "áéíóú"), None) or next((c for c in nuc if c in _ES_STRONG), nuc[-1])
    tail = _strip(sv + w[a + nuc.index(sv) + 1:])
    t = tail
    for x, y in (("ll", "y"), ("ce", "se"), ("ci", "si"), ("z", "s"), ("v", "b"), ("h", ""), ("ge", "je"),
                 ("gi", "ji"), ("c", "k"), ("x", "ks")):
        t = t.replace(x, y)
    if t.endswith("y"):
        t = t[:-1] + "i"
    vow = " ".join(c for c in t if c in "aeiou")
    return t, vow, len(vow.split())


# ------------------------------------------------------------------- words ---
def word_key(raw: str, lang: str) -> tuple[str, str, int] | None:
    """(perfect key, slant key, vowel count) or None for filler."""
    w = _plain(raw) if lang != "es" else raw.lower()
    if not w or _plain(raw) in FILLER:
        return None
    if lang == "es":
        return _es(raw)
    ph = _cmu(w) or _cmu(PATOIS.get(w, "")) or _cmu(w.replace("in'", "ing"))
    if ph:
        return _tail(ph)
    return _guess(w)


def line_lang(text: str, song_lang: str) -> str:
    if song_lang.lower().startswith("span"):
        return "es"
    toks = [_plain(t) for t in text.split()]
    es = sum(1 for t in text.lower().split() if t in ES_HINT or re.search(r"[áéíóúñ]", t))
    return "es" if es >= max(2, len(toks) // 3) else "en"


def analyze(lines: list[dict], song_lang: str = "English") -> dict:
    """Returns {"letters": [per line letter or ''], "internal": [per line list of 'a/b'], "rate": share}"""
    ends, keys = [], []
    for ln in lines:
        lang = line_lang(ln["text"], song_lang)
        toks = [t for t in ln["text"].split() if _plain(t) or lang == "es"]
        kw = None
        for t in reversed(toks):
            kw = word_key(t, lang)
            if kw:
                ends.append(_plain(t) or t.lower())
                break
        else:
            ends.append("")
        keys.append(kw)
        ln["_lang"] = lang

    slant = [k[1] if k and k[1] else None for k in keys]
    first: dict[str, int] = {}
    members: dict[str, list[int]] = {}
    for i, s in enumerate(slant):
        if s:
            members.setdefault(s, []).append(i)
            first.setdefault(s, i)
    fam = {s: m for s, m in members.items() if len(m) >= 2 and min(b - a for a, b in zip(m, m[1:])) <= 6}
    order = sorted(fam, key=lambda s: first[s])
    names = {}
    for n, s in enumerate(order):
        names[s] = _letters(n)
    letters = [names.get(s, "") if s else "" for s in slant]

    internal = []
    for i, ln in enumerate(lines):
        lang = ln.pop("_lang")
        toks = [t for t in ln["text"].split()]
        cand = []
        for t in toks:
            p = _plain(t) if lang != "es" else t.lower().strip(".,!?¡¿;:\"'")
            if len(p) < 3 or p in STOP or p in FILLER:
                continue
            k = word_key(t, lang)
            if k and k[0]:
                cand.append((p, k))
        pairs, seen = [], set()
        for a in range(len(cand)):
            for b in range(a + 1, len(cand)):
                (wa, ka), (wb, kb) = cand[a], cand[b]
                if wa == wb or wa.endswith(wb) or wb.endswith(wa):
                    continue
                if ka[0] == kb[0] or (ka[2] >= 2 and ka[1] == kb[1]):
                    pr = f"{wa}/{wb}"
                    if pr not in seen:
                        seen.add(pr)
                        pairs.append(pr)
        internal.append(pairs[:2])
    rated = sum(1 for x in letters if x)
    return {"letters": letters, "internal": internal, "ends": ends,
            "rate": rated / max(1, sum(1 for k in keys if k))}


def _letters(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def scheme(letters: list[str]) -> str:
    s = "".join(x if len(x) == 1 else f"({x})" for x in (l or "-" for l in letters))
    return s if len(s) <= 24 else s[:22] + ".."
