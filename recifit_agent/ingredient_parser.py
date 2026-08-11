"""Parses raw ingredient text (as found in the _TB_RECIPE_SEARCH dataset,
e.g. "[재료] 소고기 100 g | 불린미역 50 g | 다진마늘 1 작은술") into structured
{name, amount, unit, raw} dicts.

Deterministic regex-based parsing, not an LLM call — the output feeds unit
conversion and budget math, which must stay code-verifiable rather than
trusting a model's arithmetic (see cart_tools.py).
"""
import re

_SECTION_HEADER_RE = re.compile(r"\[[^\]]*\]")
_SPLIT_RE = re.compile(r"[|\n,]")
_UNIT_RE = re.compile(
    r"^(?P<name>.+?)\s*"
    r"(?P<amount>\d+/\d+|\d+\.\d+|\d+)?\s*"
    r"(?P<unit>g|kg|ml|l|개|봉|모|대|장|알|쪽|컵|큰술|작은술|스푼|줌|마리|팩|단|통|근|캔)?\s*$",
    re.IGNORECASE,
)
_NOISE_RE = re.compile(r"(약간|적당량|적당히|조금|취향껏)")


def _parse_amount(raw: str | None) -> float | None:
    if not raw:
        return None
    if "/" in raw:
        num, den = raw.split("/", 1)
        try:
            return round(float(num) / float(den), 4)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_ingredient_line(line: str) -> dict | None:
    raw = line.strip()
    if not raw:
        return None

    cleaned = _NOISE_RE.sub("", raw).strip()
    match = _UNIT_RE.match(cleaned)
    if not match:
        return {"name": raw, "amount": None, "unit": None, "raw": raw}

    name = match.group("name").strip(" -·")
    amount = _parse_amount(match.group("amount"))
    unit = match.group("unit")

    if not name:
        return None

    return {"name": name, "amount": amount, "unit": unit, "raw": raw}


def parse_ingredients_block(raw_block: str) -> list[dict]:
    if not raw_block:
        return []

    # Replace with a delimiter, not "" — otherwise the ingredient right
    # before a new [section] header and the one right after it (no pipe/
    # newline between them) silently merge into a single garbled entry.
    without_headers = _SECTION_HEADER_RE.sub("|", raw_block)
    lines = [p for p in _SPLIT_RE.split(without_headers) if p.strip()]

    ingredients: list[dict] = []
    for line in lines:
        parsed = parse_ingredient_line(line)
        if parsed is not None:
            ingredients.append(parsed)
    return ingredients


def parse_servings(raw: str | float | int | None) -> float:
    if raw is None:
        return 1.0
    if isinstance(raw, (int, float)):
        return float(raw) or 1.0
    match = re.search(r"(\d+(?:\.\d+)?)", str(raw))
    return float(match.group(1)) if match else 1.0
