"""Instruction following: 20 prompts, each with a script checker and a known-good and known-bad sample answer.
A checker gets the visible answer text (reasoning excluded) and returns (ok, detail)."""
import json
import re

import jsonschema

WORD = re.compile(r"[A-Za-z0-9'’-]+")


def words(s):
    return WORD.findall(s)


def sentences(s):
    """Sentences = runs ending in . ! or ?; returns (list, leftover text without an end mark)."""
    found = re.findall(r"[^.!?]*[.!?]+", s)
    rest = s[sum(len(x) for x in found):].strip()
    return [x.strip() for x in found if x.strip()], rest


def nonempty_lines(s):
    return [ln for ln in s.splitlines() if ln.strip()]


def _c01(t):
    t = t.strip()
    if re.search("[zZ]", t):
        return False, "contains z"
    ss, rest = sentences(t)
    if rest:
        return False, f"text after the last sentence: {rest[:40]!r}"
    if len(ss) != 3:
        return False, f"{len(ss)} sentences"
    counts = [len(words(x)) for x in ss]
    return all(8 <= c <= 12 for c in counts), f"word counts {counts}"


def _c02(t):
    try:
        v = json.loads(t.strip())
    except ValueError as e:
        return False, f"not JSON: {e}"
    if not (isinstance(v, list) and len(v) == 7 and all(isinstance(x, str) and x for x in v)):
        return False, "not a list of 7 non-empty strings"
    if any(x != x.lower() for x in v):
        return False, "not all lowercase"
    if len(set(v)) != 7:
        return False, "duplicates"
    return v == sorted(v), "sorted" if v == sorted(v) else "not sorted"


def _c03(t):
    if "," in t:
        return False, "contains a comma"
    ls = nonempty_lines(t)
    if len(ls) != 5:
        return False, f"{len(ls)} lines"
    first = "".join(ln.strip()[0] for ln in ls)
    return first == "RIVER", f"initials {first!r}"


SCHEMA04 = {
    "type": "object", "additionalProperties": False,
    "required": ["name", "founded", "open_days", "owner", "rating"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "founded": {"type": "integer", "minimum": 1800, "maximum": 2025},
        "open_days": {"type": "array", "minItems": 1, "maxItems": 7, "uniqueItems": True,
                      "items": {"enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}},
        "owner": {"type": "object", "additionalProperties": False, "required": ["first", "last"],
                  "properties": {"first": {"type": "string", "minLength": 1},
                                 "last": {"type": "string", "minLength": 1}}},
        "rating": {"type": "number", "minimum": 0, "maximum": 5},
    },
}


def _c04(t):
    try:
        v = json.loads(t.strip())
    except ValueError as e:
        return False, f"not JSON: {e}"
    if isinstance(v, dict) and isinstance(v.get("founded"), bool):
        return False, "founded is a boolean"
    try:
        jsonschema.validate(v, SCHEMA04)
    except jsonschema.ValidationError as e:
        return False, f"schema: {e.message[:120]}"
    return True, "valid"


def _c05(t):
    t = t.strip()
    if re.search("[eE]", t):
        return False, "contains e"
    if "\n\n" in t:
        return False, "more than one paragraph"
    n = len(words(t))
    return 40 <= n <= 60, f"{n} words"


def _c06(t):
    ls = nonempty_lines(t)
    if len(ls) != 5:
        return False, f"{len(ls)} lines"
    for ln in ls:
        s = ln.rstrip()
        if not s.startswith("- ") or not s.endswith("?"):
            return False, f"bad bullet {s[:40]!r}"
        if len(words(s[2:])) >= 10:
            return False, f"too many words: {s[:40]!r}"
    return True, "5 bullets"


def _c07(t):
    exp = "Q7#mango-Delta_19!"[::-1]
    return t.strip() == exp, f"got {t.strip()[:40]!r}"


def _c08(t):
    exp = ["| n | n^2 | n^3 |", "|---|---|---|"] + [f"| {n} | {n * n} | {n ** 3} |" for n in range(1, 7)]
    got = [ln.strip() for ln in t.strip().splitlines()]
    return got == exp, "exact" if got == exp else f"first difference near {next((g for g, e in zip(got, exp) if g != e), got[len(exp):len(exp) + 1])!r}"


def _c09(t):
    t = t.strip()
    if "\n" in t or not t.endswith("."):
        return False, "not one sentence ending with a period"
    ss, rest = sentences(t)
    if len(ss) != 1 or rest:
        return False, f"{len(ss)} sentences"
    ws = re.findall(r"[A-Za-z'’]+(?:-[A-Za-z'’]+)*", t)
    bad = [w for w in ws if w[0] not in "sS"]
    if bad:
        return False, f"words not starting with s: {bad[:3]}"
    return len(ws) >= 12, f"{len(ws)} words"


def _c10(t):
    ls = t.strip().split("\n")
    if len(ls) != 4:
        return False, f"{len(ls)} lines"
    for k, ln in enumerate(ls, 1):
        if not re.fullmatch(r"[a-z]+( [a-z]+)*", ln):
            return False, f"line {k} has characters other than lowercase letters and single spaces"
        ws = ln.split(" ")
        if len(ws) != k or any(len(w) != k + 2 for w in ws):
            return False, f"line {k}: {ws}"
    return True, "ok"


def _c11(t):
    t = t.strip()
    paras = [p for p in re.split(r"\n[ \t]*\n", t) if p.strip()]
    if len(paras) != 2 or re.search(r"\n[ \t]*\n[ \t]*\n", t):
        return False, f"{len(paras)} paragraphs"
    if re.search("[a-z]", t):
        return False, "lowercase letters present"
    n = len(words(t))
    r = len(re.findall(r"(?<![A-Z])RIVER(?![A-Z])", t))
    return 40 <= n <= 70 and r == 2, f"{n} words, RIVER x{r}"


def _c12(t):
    ls = nonempty_lines(t)
    if len(ls) != 2:
        return False, f"{len(ls)} lines"
    ws = ls[0].split()
    letters = sum(ch.isascii() and ch.isalpha() for ch in ls[0])
    if len(ws) != 6:
        return False, f"{len(ws)} words"
    return ls[1].strip() == str(letters), f"letters {letters}, stated {ls[1].strip()!r}"


def _c13(t):
    ls = [ln.strip() for ln in t.strip().splitlines()]
    if '"' in t:
        return False, "quote characters"
    if len(ls) != 5 or ls[0] != "name,age,city":
        return False, "header / row count"
    ages, cities = [], []
    for ln in ls[1:]:
        f = ln.split(",")
        if len(f) != 3 or any(not x.strip() for x in f):
            return False, f"bad row {ln!r}"
        if not re.fullmatch(r"\d+", f[1].strip()):
            return False, f"age not an integer: {f[1]!r}"
        ages.append(int(f[1]))
        cities.append(f[2].strip().lower())
    if any(b <= a for a, b in zip(ages, ages[1:])):
        return False, f"ages {ages}"
    return len(set(cities)) == 4, f"cities {cities}"


def _c14(t):
    exp = " ".join("quadsept" if n % 28 == 0 else "quad" if n % 4 == 0 else "sept" if n % 7 == 0 else str(n)
                   for n in range(1, 31))
    return t.strip() == exp, "exact" if t.strip() == exp else f"got {t.strip()[:60]!r}"


def _c15(t):
    ls = t.strip("\n").split("\n")
    ls = [ln.rstrip() for ln in ls]
    if len(ls) != 4:
        return False, f"{len(ls)} lines"
    title, rule, blank, summary = ls
    ws = re.findall(r"[A-Za-z][A-Za-z'’-]*", title)
    if not ws or any(not w[0].isupper() for w in ws):
        return False, f"title not in Title Case: {title!r}"
    if rule != "=" * len(title):
        return False, f"rule length {len(rule)} vs title {len(title)}"
    if blank.strip():
        return False, "third line not blank"
    ss, rest = sentences(summary)
    return len(ss) == 2 and not rest, f"{len(ss)} summary sentences"


def _c16(t):
    try:
        v = json.loads(t.strip())
    except ValueError as e:
        return False, f"not JSON: {e}"
    if not isinstance(v, dict) or set(v) != {"palindromes", "letters"}:
        return False, "keys"
    p = v["palindromes"]
    if not (isinstance(p, list) and len(p) == 3 and len(set(p)) == 3):
        return False, "need 3 different words"
    for w in p:
        if not (isinstance(w, str) and re.fullmatch(r"[a-z]{5,}", w) and w == w[::-1]):
            return False, f"not a lowercase palindrome of 5+ letters: {w!r}"
    ok = isinstance(v["letters"], int) and not isinstance(v["letters"], bool) and v["letters"] == sum(map(len, p))
    return ok, f"letters {v['letters']!r} vs {sum(map(len, p))}"


def _c17(t):
    ls = nonempty_lines(t)
    if len(ls) != 5:
        return False, f"{len(ls)} lines"
    last = [re.sub(r"[^a-z]", "", (re.findall(r"[A-Za-z'’]+", ln) or [""])[-1].lower()) for ln in ls]
    ok = all(last[i].endswith("ight") for i in (0, 1, 4)) and all(last[i].endswith("ay") for i in (2, 3))
    return ok, f"line endings {last}"


def _c18(t):
    ws = t.strip().split()
    if len(ws) != 12:
        return False, f"{len(ws)} words"
    return all(re.fullmatch(r"[a-z]+", w) for w in ws), "lowercase letters only" if all(
        re.fullmatch(r"[a-z]+", w) for w in ws) else "punctuation, digits or capitals"


def _c19(t):
    if re.search(r"please", t, re.I):
        return False, "uses 'please'"
    ls = t.strip("\n").split("\n")
    ls = [ln.rstrip() for ln in ls]
    if len(ls) != 7:
        return False, f"{len(ls)} lines"
    if not ls[0].startswith("Subject: ") or len(ls[0]) <= len("Subject: "):
        return False, "subject line"
    if ls[1] != "Hi Ana," or ls[2].strip() or ls[4].strip() or ls[5] != "Regards," or ls[6] != "Sam":
        return False, "fixed lines"
    ss, rest = sentences(ls[3])
    return 2 <= len(ss) <= 3 and not rest, f"{len(ss)} body sentences"


def _c20(t):
    return t.strip() == "137,131,127,113,109,107,103,101", f"got {t.strip()[:50]!r}"


ITEMS = [
    {"id": "i01_lighthouse_sentences", "check": _c01,
     "prompt": "Write exactly three sentences about lighthouses. Each sentence must contain between 8 and 12 words "
               "(inclusive), and the letter 'z' (in any case) must not appear anywhere in your reply. Output only the "
               "three sentences.",
     "good": "Lighthouses guide ships safely past rocks during dark and stormy nights. Their bright lamps once "
             "burned whale oil before electricity arrived. Many old towers now welcome curious visitors every summer.",
     "bad": "Lighthouses guide ships. Their lamps once burned oil before electricity arrived on the coast. Many "
            "towers are now museums."},
    {"id": "i02_fruit_json", "check": _c02,
     "prompt": "List seven different fruits as a JSON array of lowercase strings, sorted alphabetically. Output only "
               "the JSON array: no code fences and no other text.",
     "good": '["apple", "banana", "cherry", "grape", "kiwi", "mango", "pear"]',
     "bad": '```json\n["apple", "banana", "cherry", "grape", "kiwi", "mango", "pear"]\n```'},
    {"id": "i03_acrostic", "check": _c03,
     "prompt": "Write a poem of exactly 5 lines. The first letters of the lines, in order, must spell RIVER (one "
               "capital letter starting each line). Do not use any commas. Output only the poem.",
     "good": "Rushing past the willows\nIn silver morning light\nVanishing round the bend\nEchoing through the "
             "valley\nRolling toward the sea",
     "bad": "Rushing past the willows,\nIn silver morning light\nVanishing round the bend\nEchoing through the "
            "valley\nRolling toward the sea"},
    {"id": "i04_bookshop_schema", "check": _c04,
     "prompt": 'Create a JSON object describing a fictional bookshop with exactly these fields: "name" (a string), '
               '"founded" (an integer between 1800 and 2025), "open_days" (an array of 1 to 7 different strings, each '
               'one of "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"), "owner" (an object with exactly the fields '
               '"first" and "last", both non-empty strings) and "rating" (a number from 0 to 5). No other fields '
               "anywhere. Output only the JSON object, with no code fences and no other text.",
     "good": '{"name": "The Paper Lantern", "founded": 1952, "open_days": ["Tue", "Wed", "Sat"], '
             '"owner": {"first": "Ilse", "last": "Moreau"}, "rating": 4.5}',
     "bad": '{"name": "The Paper Lantern", "founded": "1952", "open_days": ["Tuesday"], '
            '"owner": {"first": "Ilse", "last": "Moreau", "age": 60}, "rating": 4.5}'},
    {"id": "i05_lipogram", "check": _c05,
     "prompt": "Write a single paragraph of 40 to 60 words describing a thunderstorm without using the letter 'e' "
               "(upper or lower case) anywhere. Output only the paragraph.",
     "good": "Dark clouds roll in at dusk, and a cold wind starts to blow across our town. A loud boom jolts all "
             "windows as bright flashing light rips through a black sky. Rain falls in thick, slanting columns, "
             "drumming on roofs, flooding roads, and soaking anybody out walking. By midnight it is calm again, "
             "and stars glow.",
     "bad": "Dark clouds roll in at dusk, and the wind starts to blow across our town. A loud boom shakes all "
            "windows as bright flashing light rips through a black sky. Rain falls in thick, slanting sheets, "
            "drumming on roofs, flooding roads, and soaking anybody out walking. By midnight it is calm again."},
    {"id": "i06_question_bullets", "check": _c06,
     "prompt": 'Give exactly five bullet points about saving energy at home. Each bullet must start with "- " (a '
               "hyphen and a space), be a single line, end with a question mark, and contain fewer than 10 words. "
               "Output nothing else.",
     "good": "- Have you switched to LED bulbs yet?\n- Do you unplug chargers when not using them?\n- Could a "
             "smart thermostat lower your heating bill?\n- Are your windows sealed against drafts?\n- Why not dry "
             "laundry on a line?",
     "bad": "- Have you switched to LED bulbs yet?\n- Unplug chargers when not using them.\n- Could a smart "
            "thermostat lower your heating bill?\n- Are your windows sealed against drafts?\n- Why not dry laundry "
            "on a line?"},
    {"id": "i07_reverse", "check": _c07,
     "prompt": "Write the following string reversed, character by character, and output nothing else:\n"
               "Q7#mango-Delta_19!",
     "good": "!91_atleD-ognam#7Q", "bad": "!91_atled-ognam#7Q"},
    {"id": "i08_md_table", "check": _c08,
     "prompt": "Output a Markdown table whose first line is exactly `| n | n^2 | n^3 |`, whose second line is exactly "
               "`|---|---|---|`, followed by one row for each n from 1 to 6 written like `| 2 | 4 | 8 |`. Output only "
               "the table.",
     "good": "| n | n^2 | n^3 |\n|---|---|---|\n" + "\n".join(f"| {n} | {n * n} | {n ** 3} |" for n in range(1, 7)),
     "bad": "| n | n^2 | n^3 |\n|---|---|---|\n" + "\n".join(f"| {n} | {n * n} | {n ** 3} |" for n in range(1, 6))},
    {"id": "i09_s_sentence", "check": _c09,
     "prompt": "Write one sentence of at least 12 words in which every word starts with the letter s (upper or lower "
               "case). End it with a period. Output only the sentence.",
     "good": "Seven sleepy sailors slowly sang sad songs since stormy seas swallowed several small ships.",
     "bad": "Seven sleepy sailors slowly sang sad songs because stormy seas swallowed several small ships."},
    {"id": "i10_word_ladder", "check": _c10,
     "prompt": "Output exactly 4 lines. Line k (for k = 1, 2, 3, 4) must contain exactly k words, and every word on "
               "line k must have exactly k + 2 letters. Use only lowercase letters and single spaces between words. "
               "Output nothing else.",
     "good": "sun\nboat lake\nhouse river stone\nbridge garden forest silver",
     "bad": "sun\nboat lake\nhouse river stones\nbridge garden forest silver"},
    {"id": "i11_uppercase_rivers", "check": _c11,
     "prompt": "Write exactly two paragraphs about rivers, separated by one blank line. Every letter must be "
               "uppercase. The whole reply must be 40 to 70 words long, and the word RIVER must appear exactly twice "
               "as a whole word (RIVERS does not count). Output only the two paragraphs.",
     "good": "A RIVER CARRIES WATER FROM HIGH GROUND TO THE SEA, SHAPING VALLEYS AND FEEDING FIELDS ALONG THE WAY. "
             "TOWNS GREW BESIDE THESE BANKS BECAUSE WATER MEANT LIFE.\n\nTODAY EVERY RIVER STILL MATTERS. IT "
             "SUPPLIES DRINKING WATER, MOVES CARGO, AND OFFERS QUIET PLACES TO WALK, FISH, AND REST ON A WARM "
             "AFTERNOON.",
     "bad": "A river carries water from high ground to the sea, shaping valleys and feeding fields. TOWNS GREW "
            "BESIDE THESE BANKS BECAUSE WATER MEANT LIFE.\n\nTODAY EVERY RIVER STILL MATTERS. IT SUPPLIES WATER "
            "AND MOVES CARGO AND OFFERS QUIET PLACES TO WALK."},
    {"id": "i12_six_word_story", "check": _c12,
     "prompt": "Write a six-word story on the first line. On the second line write only the total number of letters "
               "(a-z and A-Z) in your story, as digits. Output exactly these two lines.",
     "good": "Lost keys found inside frozen peas.\n29", "bad": "Lost keys found inside frozen peas.\n30"},
    {"id": "i13_csv", "check": _c13,
     "prompt": "Output a CSV table: the header line `name,age,city` followed by exactly 4 data rows. The ages must be "
               "integers that strictly increase from row to row, the four cities must all be different, no field may "
               "be empty, and do not use quote characters. Output only the CSV lines.",
     "good": "name,age,city\nAmara,24,Lagos\nBen,31,Leeds\nChiara,38,Turin\nDev,45,Pune",
     "bad": "name,age,city\nAmara,24,Lagos\nBen,31,Leeds\nChiara,31,Turin\nDev,45,Pune"},
    {"id": "i14_quadsept", "check": _c14,
     "prompt": 'Write the integers from 1 to 30 in order on a single line, separated by single spaces, but write '
               '"quad" instead of multiples of 4, "sept" instead of multiples of 7, and "quadsept" instead of '
               "multiples of both. Output nothing else.",
     "good": " ".join("quadsept" if n % 28 == 0 else "quad" if n % 4 == 0 else "sept" if n % 7 == 0 else str(n)
                      for n in range(1, 31)),
     "bad": " ".join("quad" if n % 4 == 0 else "sept" if n % 7 == 0 else str(n) for n in range(1, 31))},
    {"id": "i15_title_rule", "check": _c15,
     "prompt": "The topic is bicycles. Output a title in Title Case (every word capitalised) on the first line; on "
               "the second line, only '=' characters, exactly as many as the title has characters; then a blank "
               "line; then a summary of exactly two sentences on a single line. Output nothing else.",
     "good": "Why Bicycles Still Matter\n" + "=" * 25 + "\n\nBicycles are cheap, quiet and healthy ways to "
             "travel. Cities that build bike lanes see less traffic and cleaner air.",
     "bad": "Why Bicycles Still Matter\n" + "=" * 24 + "\n\nBicycles are cheap, quiet and healthy ways to "
            "travel. Cities that build bike lanes see less traffic and cleaner air."},
    {"id": "i16_palindromes", "check": _c16,
     "prompt": 'Return a JSON object with exactly two keys: "palindromes", a list of exactly three different English '
               'words of at least 5 letters that read the same backwards, written in lowercase; and "letters", the '
               "total number of letters in those three words (an integer). Output only the JSON object, with no code "
               "fences.",
     "good": '{"palindromes": ["level", "racecar", "rotor"], "letters": 17}',
     "bad": '{"palindromes": ["level", "racecar", "rotor"], "letters": 16}'},
    {"id": "i17_limerick", "check": _c17,
     "prompt": 'Write a limerick of exactly 5 lines. The last words of lines 1, 2 and 5 must end in the letters '
               '"ight", and the last words of lines 3 and 4 must end in "ay". Punctuation after the last word is '
               "allowed. Output only the limerick.",
     "good": "A baker who worked through the night\nWould knead until dough felt just right\nHe'd hum and he'd "
             "sway\nTill the break of the day\nThen sleep through the morning's first light.",
     "bad": "A baker who worked through the night\nWould knead until dough felt just right\nHe'd hum and he'd "
            "sway\nTill the break of the dawn\nThen sleep through the morning's first light."},
    {"id": "i18_twelve_words", "check": _c18,
     "prompt": "Topic: the ocean. Reply with exactly 12 words, all lowercase, with no punctuation of any kind and no "
               "digits.",
     "good": "the ocean breathes slowly under a silver moon and dreams of shores",
     "bad": "The ocean breathes slowly under a silver moon and dreams of shores."},
    {"id": "i19_email_format", "check": _c19,
     "prompt": "Write a short email to a colleague named Ana asking to move a meeting to Thursday. Format: the first "
               'line starts with "Subject: "; the second line is exactly "Hi Ana,"; then a blank line; then a body of '
               'two or three sentences on a single line; then a blank line; then the line "Regards," and a final line '
               '"Sam". Do not use the word "please" anywhere, in any case. Output only the email.',
     "good": "Subject: Moving our meeting to Thursday\nHi Ana,\n\nWould it be possible to move our Tuesday meeting "
             "to Thursday? Something urgent came up on my side. Any time after ten works for me.\n\nRegards,\nSam",
     "bad": "Subject: Moving our meeting to Thursday\nHi Ana,\n\nCould you please move our Tuesday meeting to "
            "Thursday? Something urgent came up on my side.\n\nRegards,\nSam"},
    {"id": "i20_primes_desc", "check": _c20,
     "prompt": "List the eight smallest prime numbers greater than 100 in descending order, separated by commas with "
               "no spaces. Output nothing else.",
     "good": "137,131,127,113,109,107,103,101", "bad": "139,137,131,127,113,109,107,103"},
]
