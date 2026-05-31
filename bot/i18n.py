from pathlib import Path

import yaml

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
_cache: dict[str, dict[str, str]] = {}


LOCALES = ("ru", "en", "ua")


def load_locale(lang: str) -> dict[str, str]:
    code = lang if lang in LOCALES else "en"
    if code not in _cache:
        path = LOCALES_DIR / f"{code}.yaml"
        with path.open(encoding="utf-8") as f:
            _cache[code] = yaml.safe_load(f) or {}
    return _cache[code]


def t(lang: str, key: str, **kwargs: object) -> str:
    strings = load_locale(lang)
    template = strings.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
