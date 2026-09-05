"""CoreDB — parse Module:ObjectInfo/data (Lua) from core-keeper.fandom.com into JSON.

The Fandom wiki stores ALL game data (items, weapons, armor, food, enemies,
recipes, drops) in one giant Lua data module. We parse it into clean JSON.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "scripts" / "cache"
CACHE.mkdir(exist_ok=True)
LUA_FILE = CACHE / "objectinfo.lua"
DATA_DIR = ROOT / "src" / "data"
DATA_DIR.mkdir(exist_ok=True)

WIKI_URL = (
    "https://core-keeper.fandom.com/api.php?action=parse"
    "&page=Module:ObjectInfo/data&prop=wikitext&format=json"
)
PROXY = "http://127.0.0.1:7897"


def fetch_lua() -> str:
    if LUA_FILE.exists() and LUA_FILE.stat().st_size > 100000:
        print(f"[cache] using {LUA_FILE}")
        return LUA_FILE.read_text(encoding="utf-8")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    req = urllib.request.Request(
        WIKI_URL,
        headers={
            "User-Agent": "CoreDB/1.0 (site builder; contact: franceiwhdbks865@gmail.com)",
            "Accept": "application/json",
        },
    )
    with opener.open(req, timeout=120) as r:
        payload = json.loads(r.read().decode("utf-8"))
    lua = payload["parse"]["wikitext"]["*"]
    LUA_FILE.write_text(lua, encoding="utf-8")
    print(f"[fetch] saved {len(lua)} chars")
    return lua


# ---------------------------------------------------------------- Lua parser
class Parser:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    def skip_ws(self):
        while self.i < self.n:
            c = self.s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "-" and self.s[self.i : self.i + 2] == "--":
                j = self.s.find("\n", self.i)
                self.i = self.n if j == -1 else j + 1
            else:
                break

    def parse(self):
        self.skip_ws()
        assert self.s[self.i : self.i + 6] == "return", "expected 'return'"
        self.i += 6
        v = self.parse_value()
        return v

    def parse_value(self):
        self.skip_ws()
        c = self.s[self.i]
        if c == "{":
            return self.parse_table()
        if c == '"':
            return self.parse_string()
        if self.s.startswith("true", self.i):
            self.i += 4
            return True
        if self.s.startswith("false", self.i):
            self.i += 5
            return False
        m = re.match(r"-?\d+(?:\.\d+)?", self.s[self.i :])
        if m:
            tok = m.group(0)
            self.i += len(tok)
            return float(tok) if "." in tok else int(tok)
        raise SyntaxError(f"unexpected char at {self.i}: {self.s[self.i:self.i+30]!r}")

    def parse_string(self):
        i = self.i + 1
        out = []
        while True:
            c = self.s[i]
            if c == "\\":
                nxt = self.s[i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                i += 2
            elif c == '"':
                self.i = i + 1
                return "".join(out)
            else:
                out.append(c)
                i += 1

    def parse_table(self):
        self.i += 1  # consume {
        result: dict | list
        used = set()
        numeric_keys = True
        pairs = []
        expect_index = 0
        while True:
            self.skip_ws()
            if self.s[self.i] == "}":
                self.i += 1
                break
            # key?
            key = None
            if self.s[self.i] == "[":
                self.i += 1
                k = self.parse_value()
                self.skip_ws()
                assert self.s[self.i] == "]"
                self.i += 1
                key = k
                if not isinstance(k, int):
                    numeric_keys = False
            else:
                m = re.match(r"[A-Za-z_]\w*", self.s[self.i :])
                if m:
                    after = self.i + m.end()
                    self.skip_ws()
                    if self.s[after] == "=":
                        key = m.group(0)
                        numeric_keys = False
                        self.i = after
            if key is not None:
                self.skip_ws()
                assert self.s[self.i] == "=", f"expected = at {self.i}: {self.s[self.i:self.i+20]!r}"
                self.i += 1
            val = self.parse_value()
            pairs.append((key, val))
            self.skip_ws()
            c = self.s[self.i]
            if c == "," or c == ";":
                self.i += 1
            elif c == "}":
                self.i += 1
                break
            else:
                raise SyntaxError(f"expected , or }} at {self.i}: {self.s[self.i:self.i+20]!r}")
        if numeric_keys:
            keys = [k for (k, _v) in pairs]
            if any(k is None for k in keys):
                return [v for (_k, v) in pairs]
            if keys and min(keys) in (0, 1) and keys == list(range(min(keys), min(keys) + len(keys))):
                return [v for (_k, v) in pairs]
            result = {str(k): v for (k, v) in pairs}
            return result
        result = {}
        for k, v in pairs:
            if k is None:
                result[str(expect_index)] = v
                expect_index += 1
            else:
                result[str(k)] = v
        return result


# ------------------------------------------------------------- dataset build
def get(o, *keys, default=None):
    for k in keys:
        if o is None:
            return default
        if isinstance(o, dict):
            o = o.get(k)
        else:
            return default
    return o if o is not None else default


def max_of(v):
    if not isinstance(v, dict):
        return v
    nums = []
    for x in v.values():
        if isinstance(x, (int, float)):
            nums.append(x)
        elif isinstance(x, dict):
            m = max_of(x)
            if m is not None:
                nums.append(m)
    return max(nums) if nums else None


def condition_summary(equipped):
    """Flatten equipped.conditions into {id: max_value}."""
    out = {}
    for cond in get(equipped, "conditions", default=[]) or []:
        cid = cond.get("id")
        val = max_of(cond.get("value"))
        if cid and val is not None:
            out[cid] = max(out.get(cid, 0), val)
    return out


def base_stats(obj):
    """Pick the base (lowest-level) entry from meleeDamage etc. dicts."""
    if not isinstance(obj, dict):
        return obj
    lv = [(int(k), v) for k, v in obj.items()]
    lv.sort()
    return lv[0][1] if lv else None


def at_max(obj):
    if isinstance(obj, dict) and obj:
        try:
            return obj[str(max(int(k) for k in obj))]
        except Exception:
            return None
    return None


def scale_range(obj):
    """(base_level, base_value, max_level, max_value) for a per-level dict."""
    if not isinstance(obj, dict) or not obj:
        return None
    lv = sorted((int(k), v) for k, v in obj.items())
    b, m = lv[0], lv[-1]
    return (b[0], b[1], m[0], m[1])


def slugify(name):
    return name.replace(" ", "_").replace("'", "").lstrip(".").strip()


def main():
    lua = fetch_lua()
    print("[parse] parsing Lua table ...")
    data = Parser(lua).parse()
    print(f"[parse] top-level keys: {len(data)}")

    items = {}
    creatures = {}
    for key, variants in data.items():
        if isinstance(variants, list):
            entry = variants[0] if variants else None
        elif isinstance(variants, dict):
            entry = variants.get("0")
            if entry is None and len(variants) == 1:
                entry = next(iter(variants.values()))
        else:
            entry = None
        if not isinstance(entry, dict):
            continue
        if entry.get("enemy") or entry.get("boss") or entry.get("pet") or entry.get("cattle"):
            creatures[key] = entry
        else:
            items[key] = entry
    print(f"[split] items: {len(items)}, creatures: {len(creatures)}")

    # quick inventory of categories / types for weapon/armor/food routing
    from collections import Counter

    cats = Counter()
    types = Counter()
    for it in items.values():
        for c in get(it, "categories", default=[]) or []:
            cats[c] += 1
        types[get(it, "type")] += 1
    print("[cats] top:", cats.most_common(30))
    print("[types] top:", types.most_common(40))

    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "objects_raw.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    (DATA_DIR / "creatures_raw.json").write_text(
        json.dumps(creatures, ensure_ascii=False), encoding="utf-8"
    )
    print("[done] wrote objects_raw.json / creatures_raw.json")


if __name__ == "__main__":
    main()
