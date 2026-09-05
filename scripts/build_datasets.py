"""CoreDB — build clean datasets from objects_raw.json / creatures_raw.json.

Outputs into src/data/:
  weapons.json, armor.json, accessories.json, food.json, enemies.json,
  calculator.json (recipes + item names), meta.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "data"

WEAPON_TYPES = {
    "MeleeWeapon": "Melee",
    "RangeWeapon": "Ranged",
    "ThrowingWeapon": "Throwing",
    "SummoningWeapon": "Summoning",
    "BeamWeapon": "Beam",
}
ARMOR_SLOTS = {"Helm": "Helm", "BreastArmor": "Breast", "PantsArmor": "Pants"}
ACC_TYPES = {"Ring": "Ring", "Necklace": "Necklace", "Offhand": "Offhand"}

FOOD_BUFF_LABELS = {
    "HungerAddition": "hunger",
    "HealOverTime": "heal over time",
    "HealthReduction": "health loss",
    "BlueGlow": "blue glow",
    "VoidGlow": "void glow",
    "CritChance": "crit chance",
    "AllDamageIncrease": "all damage",
    "LifeOnHit": "life on hit",
    "ArmorIncrease": "armor",
    "AttackSpeed": "attack speed",
    "IncreasedMaxHealthPermanent": "permanent max health",
    "MovementSpeedDecrease": "movement speed down",
    "HealthAdditionPercentage": "health %",
    "ImmuneToBurning": "burning immunity",
    "ManaAdditionPercentage": "mana %",
    "IncreasedMaxHealth": "max health",
    "RemovePoison": "cure poison",
}


def slugify(name: str) -> str:
    return name.replace(" ", "_").replace("'", "").replace(".", "").strip()


def per_level(d):
    """Normalize {level: value} dict -> (base_level, base, max_level, max, levels)."""
    if not isinstance(d, dict) or not d:
        return None
    try:
        lv = sorted((int(k), v) for k, v in d.items())
    except (ValueError, TypeError):
        return None
    if not lv:
        return None
    b, m = lv[0], lv[-1]
    return {
        "baseLevel": b[0],
        "base": b[1],
        "maxLevel": m[0],
        "max": m[1],
        "levels": {str(k): v for k, v in lv},
    }


def cond_map(entry, bucket="equipped"):
    """Collect conditions from equipped/consumed into {id: per_level_or_value}."""
    src = entry.get(bucket) or {}
    conds = src.get("conditions") or []
    out = {}
    for c in conds:
        cid = c.get("id")
        if not cid:
            continue
        pl = per_level(c.get("value"))
        if pl:
            out[cid] = pl
        elif isinstance(c.get("value"), (int, float)):
            out[cid] = {
                "baseLevel": None,
                "base": c["value"],
                "maxLevel": None,
                "max": c["value"],
                "levels": {"0": c["value"]},
            }
    return out


def common(entry):
    return {
        "name": entry.get("name"),
        "slug": slugify(entry.get("name") or ""),
        "desc": (entry.get("description") or "").strip(),
        "rarity": entry.get("rarity"),
        "level": entry.get("level"),
        "area": entry.get("area"),
        "sell": entry.get("sell"),
        "materials": entry.get("materials"),
        "durability": entry.get("durability"),
        "type": entry.get("type"),
        "categories": entry.get("categories") or [],
    }


def build():
    items = json.loads((DATA / "objects_raw.json").read_text(encoding="utf-8"))
    creatures = json.loads((DATA / "creatures_raw.json").read_text(encoding="utf-8"))

    weapons, armor, accessories, food = [], [], [], []
    recipes = []
    name_map = {}

    for key, e in items.items():
        cm = common(e)
        name_map[key] = cm["name"]
        t = e.get("type")
        cats = e.get("categories") or []

        if t in WEAPON_TYPES and "NonObtainable" not in cats:
            dmg_key = (
                "meleeDamage"
                if "meleeDamage" in e
                else ("rangeDamage" if "rangeDamage" in e else None)
            )
            if dmg_key is None:
                dmg_key = next((k for k in ("magicDamage", "damage") if k in e), None)
            dmg = per_level(e.get(dmg_key)) if dmg_key else None
            cd = e.get("cooldown")
            rec = {
                **cm,
                "group": WEAPON_TYPES[t],
                "dmg": dmg,
                "dps": round(dmg["max"] / cd, 1) if dmg and cd else None,
                "cooldown": cd,
                "conds": cond_map(e),
                "secondaryUse": bool(e.get("secondaryUse")),
            }
            weapons.append(rec)
            recipes.append({"key": key, "name": cm["name"], "materials": e.get("materials")})

        elif t in ARMOR_SLOTS and "NonObtainable" not in cats:
            conds = cond_map(e)
            rec = {
                **cm,
                "slot": ARMOR_SLOTS[t],
                "armor": conds.get("ArmorIncrease"),
                "maxHealth": conds.get("IncreasedMaxHealth"),
                "conds": conds,
            }
            armor.append(rec)
            recipes.append({"key": key, "name": cm["name"], "materials": e.get("materials")})

        elif t in ACC_TYPES and "NonObtainable" not in cats:
            rec = {**cm, "slot": ACC_TYPES[t], "conds": cond_map(e)}
            accessories.append(rec)
            recipes.append({"key": key, "name": cm["name"], "materials": e.get("materials")})

        elif t == "Eatable" and "NonObtainable" not in cats:
            conds = cond_map(e, "consumed")
            hunger = (conds.pop("HungerAddition", None) or {}).get("base")
            rec = {
                **cm,
                "hunger": hunger,
                "buffs": {FOOD_BUFF_LABELS.get(k, k): v for k, v in conds.items()},
                "cooked": "CookedFood" in cats,
                "petXp": e.get("petXp"),
            }
            food.append(rec)
            recipes.append({"key": key, "name": cm["name"], "materials": e.get("materials")})
        elif e.get("materials"):
            recipes.append({"key": key, "name": cm["name"], "materials": e.get("materials")})

    enemies = []
    for key, c in creatures.items():
        if not c.get("enemy") or c.get("pet") or c.get("cattle"):
            continue
        drops = []
        for d in ((c.get("loot") or {}).get("drops") or []):
            if d.get("id"):
                drops.append(
                    {
                        "id": d["id"],
                        "amount": d.get("amount"),
                        "chance": d.get("chance"),
                    }
                )
                name_map.setdefault(d["id"], d["id"])
        enemies.append(
            {
                "name": c.get("name") or key,
                "slug": slugify(c.get("name") or key),
                "desc": (c.get("description") or "").strip(),
                "boss": bool(c.get("boss")),
                "level": c.get("level"),
                "area": c.get("area"),
                "faction": c.get("faction"),
                "health": c.get("health"),
                "moveSpeed": c.get("moveSpeed"),
                "drops": drops,
            }
        )
        name_map.setdefault(key, c.get("name") or key)

    weapons.sort(key=lambda x: -(x["dps"] or 0))
    armor.sort(key=lambda x: -(x["armor"]["max"] if x["armor"] else 0))
    food.sort(key=lambda x: -(x["hunger"] or 0))
    enemies.sort(key=lambda x: (not x["boss"], -(x["health"] or 0)))

    calc = {
        "names": name_map,
        "recipes": [r for r in recipes if r["materials"]],
    }

    for fname, payload in [
        ("weapons.json", weapons),
        ("armor.json", armor),
        ("accessories.json", accessories),
        ("food.json", food),
        ("enemies.json", enemies),
        ("calculator.json", calc),
    ]:
        (DATA / fname).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"[write] {fname}: {len(payload)}")

    meta = {
        "gameVersion": "1.2.0.7",
        "counts": {
            "weapons": len(weapons),
            "armor": len(armor),
            "accessories": len(accessories),
            "food": len(food),
            "enemies": len(enemies),
        },
    }
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("[meta]", meta)


if __name__ == "__main__":
    build()
