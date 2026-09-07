#!/usr/bin/env python3
"""CoreDB icon fetch v3: probe File:<name>.png existence (Fandom treats spaces/underscores
as identical). Items without a File:<name> are skipped."""
import json, re, time, urllib.request, urllib.parse
from pathlib import Path

UA = "CoreDB/1.0 (site: core-keeper-db.pages.dev; contact franceiwhdbks865@gmail.com)"
API = "https://core-keeper.fandom.com/api.php"
ROOT = Path("C:/Users/梁会斌/Documents/Codex/core-keeper-db")
DATA = ROOT / "src/data"
ICON_DIR = ROOT / "public/icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)
DELAY = 0.4

def api(p, retries=3):
    url = API + "?" + urllib.parse.urlencode({**p, "format": "json"})
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            if i == retries - 1:
                return None
            time.sleep(2 * (i + 1))

def safe_name(t):
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_") + ".png"

def main():
    datasets = ["weapons", "armor", "accessories", "food", "enemies"]
    flat = []  # (ds, item)
    for ds in datasets:
        d = json.load(open(DATA / f"{ds}.json", encoding="utf-8"))
        missing = [it for it in d if not it.get("icon")]
        print(f"{ds}: {len(d)} items, {len(missing)} missing")
        flat += [(ds, it) for it in missing]

    # Probe File:<name>.png in batches of 50, via action=query
    exist = {}  # normalized lowercase name -> True
    for start in range(0, len(flat), 50):
        chunk = flat[start:start + 50]
        titles = [f"File:{it['name']}.png" for _, it in chunk]
        r = api({"action": "query", "titles": "|".join(titles)})
        if not r:
            time.sleep(1); continue
        for pg in r.get("query", {}).get("pages", {}).values():
            if "missing" not in pg:
                title = pg["title"]  # e.g. "File:Tin Dagger.png"
                key = re.sub(r"^File:", "", title).lower().replace(".png", "")
                exist[key] = title
        time.sleep(DELAY)
    print(f"existing File:<name>.png: {len(exist)}/{len(flat)}")

    # Resolve to download URLs
    wanted = []  # list of (ds, item, filetitle)
    for ds, it in flat:
        key = it["name"].lower()
        ft = exist.get(key)
        if ft:
            wanted.append((ds, it, ft))
    print(f"to download: {len(wanted)}")

    # fetch imageinfo URL in batches of 50
    urlmap = {}
    ft_list = sorted(set(w[2] for w in wanted))
    for start in range(0, len(ft_list), 50):
        chunk = ft_list[start:start + 50]
        r = api({"action": "query", "titles": "|".join(chunk), "prop": "imageinfo", "iiprop": "url", "iiurlwidth": "120"})
        if r:
            for pg in r.get("query", {}).get("pages", {}).values():
                ii = pg.get("imageinfo")
                if ii:
                    raw = ii[0].get("url") or ""
                    urlmap[pg["title"]] = raw
        time.sleep(DELAY)

    def thumb_url(raw):
        """Rebuild the standard Fandom thumb URL from the raw image url.
        raw: .../images/<h>/<hh>/<File>.png/revision/latest?cb=...  →  .../images/thumb/<h>/<hh>/<File>.png/120px-<File>"""
        m = re.search(r"images/(?:thumb/)?([0-9a-f]/[0-9a-f]{2}/[^/]+\.png)", raw)
        if not m:
            return None
        rel = m.group(1)  # e.g. 9/9b/Tin_Dagger.png
        fname = rel.split("/")[-1]
        return f"https://static.wikia.nocookie.net/core-keeper/images/thumb/{rel}/120px-{urllib.parse.quote(fname)}"

    fetched = 0
    for ds, it, ft in wanted:
        raw = urlmap.get(ft)
        url = thumb_url(raw) if raw else None
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            b = urllib.request.urlopen(req, timeout=40).read()
            if len(b) > 300:  # skip tiny placeholder WEBPs
                (ICON_DIR / safe_name(it["slug"])).write_bytes(b)
                fetched += 1
        except Exception:
            pass
        time.sleep(0.12)
    print(f"downloaded: {fetched}")

    # Patch datasets
    for ds in datasets:
        d = json.load(open(DATA / f"{ds}.json", encoding="utf-8"))
        patched = 0
        for it in d:
            if it.get("icon"):
                continue
            fname = safe_name(it["slug"])
            if (ICON_DIR / fname).exists():
                it["icon"] = "/icons/" + fname
                patched += 1
        json.dump(d, open(DATA / f"{ds}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        have = sum(1 for it in d if it.get("icon"))
        print(f"{ds}: now {have}/{len(d)} (+{patched})")

if __name__ == "__main__":
    main()