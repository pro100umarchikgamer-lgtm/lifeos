"""Validate complete installed packs; --release also requires all launch locales."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)

def placeholders(text):
    return set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", text))

def validate(release=False, directory=None):
    directory = directory or ROOT / "assets/locales"
    packs = {p.stem: read(p) for p in sorted(directory.glob("*.json"))}
    if "en" not in packs:
        raise ValueError("missing English fallback")
    base = packs["en"]
    allowed_forms = {"zero", "one", "two", "few", "many", "other"}
    for tag, pack in packs.items():
        if pack["locale"] != tag or pack["schemaVersion"] != 1:
            raise ValueError(f"{tag}: invalid locale/schema")
        if type(pack["packVersion"]) is not int or pack["packVersion"] < 1 or not pack["nativeName"]:
            raise ValueError(f"{tag}: invalid version/name")
        if set(pack["strings"]) != set(base["strings"]) or set(pack["plurals"]) != set(base["plurals"]):
            raise ValueError(f"{tag}: incomplete keys")
        for key, text in pack["strings"].items():
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{tag}.{key}: empty/non-string")
            if placeholders(text) != placeholders(base["strings"][key]):
                raise ValueError(f"{tag}.{key}: placeholder mismatch")
        for key, forms in pack["plurals"].items():
            if "other" not in forms or not set(forms) <= allowed_forms:
                raise ValueError(f"{tag}.{key}: invalid plural forms")
            required = {"one", "few", "many", "other"} if tag in {"ru", "uk"} else {"other"}
            if not required <= set(forms):
                raise ValueError(f"{tag}.{key}: missing plural forms")
            reference = placeholders(base["plurals"][key]["other"])
            for text in forms.values():
                if not isinstance(text, str) or not text.strip() or placeholders(text) != reference:
                    raise ValueError(f"{tag}.{key}: invalid plural placeholder/text")
    if release:
        expected = set(read(ROOT / "tool/launch_locales.json"))
        if not expected <= set(packs):
            raise ValueError(f"missing launch locales: {', '.join(sorted(expected - set(packs)))}")
    return len(packs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    try:
        print(f"Validated packs: {validate(parser.parse_args().release)}")
    except (ValueError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
