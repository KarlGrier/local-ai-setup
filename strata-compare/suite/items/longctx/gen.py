"""Generate the two long-context documents and their questions (deterministic: fixed seeds).

    python3 gen.py [--target-chars N]

Writes docs/doc_a.txt, docs/doc_b.txt and questions.json (answers computed here, from the generated text's own
events).  Doc A is a research-station operations log; doc B a city chronicle.  Each has:
  * several needles (five facts, each with a near-miss distractor stated elsewhere: an old value, another locker...),
  * a counting question (mentions of one species / one bridge, with look-alike distractors),
  * a tracking question (a quantity changed by relative updates, absolute re-counts and distractor quantities).
"""
import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

PEOPLE = ["Ahmadi", "Bergstrom", "Castellanos", "Dubois", "Eriksen", "Fofana", "Gallagher", "Haddad", "Ivanova",
          "Jansen", "Kowalczyk", "Lindqvist", "Mbeki", "Nakamura", "Okonkwo", "Petrov", "Quispe", "Rasmussen",
          "Sato", "Tremblay", "Uddin", "Varga", "Whitlock", "Yilmaz", "Zielinski"]
SKY = ["clear", "overcast", "light snow", "broken cloud", "fog", "blowing snow", "high cirrus", "drizzle"]
DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "NNW", "ESE"]
PARTS = ["drive belt", "fuel filter", "pressure valve", "heating coil", "circuit breaker", "air intake screen",
         "coolant hose", "bearing", "antenna cable", "solar charge controller", "door seal", "pump impeller"]
EQUIP = ["east anemometer mast", "water maker", "greenhouse heater", "main generator", "workshop compressor",
         "seismograph vault", "incinerator", "aurora camera", "laundry dryer", "snow melter", "garage door motor"]
SITES = ["the moraine", "Gull Ridge", "the tide gauge", "Lake Sorrow", "the north ice edge", "Penguin Bay",
         "the old hut", "Basalt Point", "the meltwater stream", "Cairn Hill", "the radar dome"]
PROJECTS = ["lichen growth", "permafrost temperature", "sea ice thickness", "atmospheric ozone", "krill density",
            "snow chemistry", "seal census", "magnetometer drift"]
MEALS = ["lentil stew", "fresh bread and soup", "curry night", "pancakes", "fish pie", "pizza", "roast vegetables",
         "chili", "dumplings", "barley risotto"]
ACTIVITIES = ["led the weekly fire drill", "gave a talk on glacier dynamics", "repaired the lounge projector",
              "cut everyone's hair in the workshop", "organised a chess tournament", "cleaned the darkroom",
              "updated the medical inventory", "trained two people on the crane", "fixed the sauna thermostat",
              "wrote the monthly report", "taught a knot-tying class", "calibrated the pyranometer"]
ITEMS = ["tinned tomatoes", "rice", "flour", "batteries", "cable ties", "coffee", "lab gloves", "bin liners",
         "toilet paper", "printer paper", "sugar", "oats"]
VEHICLES = ["SM-1", "SM-2", "SM-3", "Hagglund 7", "quad bike B"]
OTHER_BIRDS = ["Antarctic petrels", "giant petrels", "snow buntings", "Wilson's storm petrels", "snowy sheathbills",
               "skuas", "Cape petrels", "Adelie penguins", "Antarctic terns"]


def doc_a(rng: random.Random, target_chars: int):
    entries = []          # (sort_key, text)
    # filler generators ------------------------------------------------------------------------------------------
    def filler():
        k = rng.randrange(10)
        p = rng.choice(PEOPLE)
        if k == 0:
            return (f"Weather observation: {rng.choice(SKY)}, air temperature {rng.uniform(-28, 4):.1f} °C, wind "
                    f"{rng.randint(0, 45)} knots from the {rng.choice(DIRS)}, visibility {rng.randint(1, 40)} km.")
        if k == 1:
            return (f"{p} replaced the {rng.choice(PARTS)} on the {rng.choice(EQUIP)}; "
                    f"{rng.choice(['working normally again', 'still noisy, to be checked tomorrow', 'tested for an hour without faults', 'old part kept as a spare'])}.")
        if k == 2:
            return (f"Scheduled radio check with {rng.choice(['the coastal base', 'the supply office', 'the sister station', 'the aircraft operator'])} "
                    f"completed; signal {rng.choice(['clear', 'weak but readable', 'strong', 'intermittent'])}.")
        if k == 3:
            return (f"{p} logged {rng.randint(2, 40)} samples from {rng.choice(SITES)} for the "
                    f"{rng.choice(PROJECTS)} project.")
        if k == 4:
            return f"Galley: {rng.choice(MEALS)} served; {p} on kitchen duty."
        if k == 5:
            return f"{p} {rng.choice(ACTIVITIES)}."
        if k == 6:
            return (f"Inventory: {rng.randint(2, 60)} cases of {rng.choice(ITEMS)} counted in store room "
                    f"{rng.choice('ABCD')}.")
        if k == 7:
            return (f"Vehicle {rng.choice(VEHICLES)} returned from {rng.choice(SITES)} after "
                    f"{rng.randint(1, 9)} hours; {rng.choice(['no issues', 'track tension adjusted', 'one ski scratched', 'refuelled from jerry cans'])}.")
        if k == 8:
            n = rng.randint(1, 30)
            return f"Wildlife: {n} {rng.choice(OTHER_BIRDS)} seen near {rng.choice(SITES)}."
        return (f"{p} and {rng.choice(PEOPLE)} walked the {rng.choice(['flag line', 'cable route', 'fuel line', 'perimeter'])} "
                f"and {rng.choice(['found nothing unusual', 'replaced two marker flags', 'cleared drifted snow', 'photographed a cracked post'])}.")

    # build the filler log until the target size --------------------------------------------------------------
    texts = []
    size = 0
    while size < target_chars:
        t = filler()
        texts.append(t)
        size += len(t) + 24
    n = len(texts)

    # counting: snow petrel mentions in distinct entries --------------------------------------------------------
    petrel_idx = sorted(rng.sample(range(n), 43))
    for i in petrel_idx:
        k = rng.randrange(3)
        if k == 0:
            texts[i] = f"Wildlife: {rng.randint(2, 14)} snow petrels seen near {rng.choice(SITES)}."
        elif k == 1:
            texts[i] = f"Wildlife: a single snow petrel circling over {rng.choice(SITES)} for most of the afternoon."
        else:
            texts[i] = (f"Wildlife: {rng.randint(2, 9)} {rng.choice(OTHER_BIRDS)} and {rng.randint(1, 5)} snow petrels "
                        f"near {rng.choice(SITES)}.")
    petrel_count = len(petrel_idx)

    # tracking: the main fuel tank -----------------------------------------------------------------------------
    main = 12000
    fuel_idx = sorted(rng.sample([i for i in range(n) if i not in set(petrel_idx)], 75))
    recount_at = set(rng.sample(fuel_idx[10:-5], 3))
    aux_idx = set(rng.sample([i for i in range(n) if i not in set(petrel_idx) | set(fuel_idx)], 20))
    fuel_text = {}
    for i in fuel_idx:
        if i in recount_at:
            main = max(0, main + rng.randint(-300, 300))
            main -= main % 10
            fuel_text[i] = f"Fuel: main tank gauge recalibrated; the corrected reading is {main:,} L."
            continue
        r = rng.random()
        if r < 0.45 or main < 2500:
            x = rng.randint(20, 90) * 10
            if main - x < 500:
                x = rng.randint(50, 200) * 10
                main += x
                fuel_text[i] = f"Fuel: tanker delivery pumped {x:,} L into the main tank."
                continue
            main -= x
            fuel_text[i] = f"Fuel: generator run drew {x:,} L from the main tank overnight."
        elif r < 0.75:
            x = rng.randint(5, 40) * 10
            main -= x
            fuel_text[i] = f"Fuel: {x:,} L transferred from the main tank to the vehicle depot drums."
        else:
            x = rng.randint(50, 200) * 10
            main += x
            fuel_text[i] = f"Fuel: tanker delivery pumped {x:,} L into the main tank."
    for i, t in fuel_text.items():
        texts[i] = t
    for i in aux_idx:
        x = rng.randint(10, 90) * 10
        texts[i] = rng.choice([f"Fuel: {x:,} L added to the auxiliary tank behind the garage.",
                               f"Fuel: auxiliary tank drained by {x:,} L for cleaning.",
                               f"Fuel: the auxiliary tank now reads {x * 3:,} L after the top-up."])
    fuel_final = main

    # needles with near-miss distractors ------------------------------------------------------------------------
    used = set(petrel_idx) | set(fuel_idx) | aux_idx
    free = [i for i in range(n) if i not in used]
    def spot(frac):
        target = int(frac * n)
        return min(free, key=lambda i: abs(i - target))
    needles = [
        (0.09, "Security: the red equipment locker keeps its combination 3-3-0-8."),
        (0.18, "Security: the combination of the blue equipment locker was changed to 4-1-7-9 today."),
        (0.27, "Science: Dr. Petrov's ice core sample was given the archive number KP-1874."),
        (0.40, "Science: Dr. Okonkwo's ice core sample was given the archive number KP-2209."),
        (0.47, "Maintenance: the main generator's serial plate reads GX-40213."),
        (0.58, "Maintenance: the backup generator's serial plate was cleaned and reads GX-55871."),
        (0.66, "Logistics: the supply ship for the summer season is the Polar Wren."),
        (0.79, "Logistics: the supply ship booked for the winter season is the Morning Albatross."),
        (0.12, "Radio: the emergency frequency is still 7.215 MHz until the new licence arrives."),
        (0.88, "Radio: the new licence arrived and the emergency frequency was changed to 8.364 MHz."),
    ]
    for frac, t in needles:
        i = spot(frac)
        texts[i] = t
        free.remove(i)

    # timestamps ----------------------------------------------------------------------------------------------
    lines = []
    day, minute = 1, 6 * 60
    for t in texts:
        minute += rng.randint(15, 140)
        if minute >= 23 * 60:
            day += 1
            minute = 6 * 60 + rng.randint(0, 60)
        lines.append(f"Day {day}, {minute // 60:02d}:{minute % 60:02d} - {t}")
    header = ("KESTREL POINT RESEARCH STATION - OPERATIONS LOG, SEASON 14\n"
              "Kept by the station leader and the duty officers. One entry per line. At the start of the season the "
              "main fuel tank held 12,000 L and the auxiliary tank was empty.\n\n")
    text = header + "\n".join(lines) + "\n\nEND OF LOG\n"
    answers = {"needles": {"locker_combination": "4-1-7-9", "ice_core_archive": "KP-2209",
                           "generator_serial": "GX-55871", "supply_ship": "Morning Albatross",
                           "radio_frequency_mhz": "8.364"},
               "count": petrel_count, "track": fuel_final}
    # sanity: the phrase occurs exactly once in each counted entry and nowhere else
    assert sum(ln.count("snow petrel") for ln in lines) == petrel_count
    return text, answers


NAMES = ["Aldric", "Brenna", "Cassian", "Doria", "Edmund", "Fenna", "Gideon", "Hesper", "Ilian", "Jessamy", "Kester",
         "Linnet", "Magnus", "Nerys", "Osric", "Perrin", "Quenna", "Rowan", "Sabine", "Tobias", "Ulla", "Veyl",
         "Wren", "Yorick"]
SURN = ["Ashdown", "Blackwater", "Corran", "Dunmere", "Ellery", "Fairholt", "Greaves", "Harrow", "Ironside",
        "Kestwick", "Loame", "Merrow", "Northam", "Oakhurst", "Pellam", "Quarry", "Rooke", "Stannard", "Thorne",
        "Underhill", "Vance", "Whitmore"]
GUILDS = ["Weavers", "Coopers", "Chandlers", "Masons", "Tanners", "Glassblowers", "Bargemen", "Bakers"]
PLACES = ["the Old Market", "the Saltgate", "the Lantern Tower", "the river quays", "the Temple of the Tides",
          "Marrowgate", "Barrow Bridge", "Marrow Street", "the Hill Ward", "the Copper Docks", "the Guildhall",
          "the Westwall", "the Orchard Ward"]


def doc_b(rng: random.Random, target_chars: int):
    def person():
        return f"{rng.choice(NAMES)} {rng.choice(SURN)}"

    def sentence():
        k = rng.randrange(11)
        if k == 0:
            return rng.choice(["The harvest was poor after a wet spring.", "The harvest was the richest anyone could "
                               "remember.", "Blight took half the barley in the eastern fields.",
                               "A late frost ruined the orchards of the Orchard Ward."])
        if k == 1:
            g1, g2 = rng.sample(GUILDS, 2)
            return f"The {g1} and the {g2} quarrelled over the right to use {rng.choice(PLACES)} on market days."
        if k == 2:
            return f"{person()} was elected speaker of the council by {rng.randint(9, 30)} votes to {rng.randint(1, 8)}."
        if k == 3:
            return f"A great fire burned {rng.randint(3, 40)} houses near {rng.choice(PLACES)} before the rains came."
        if k == 4:
            return (f"The festival of {rng.choice(['First Lanterns', 'the Long Night', 'the Returning Barges', 'Salt and Honey'])} "
                    f"drew crowds to {rng.choice(PLACES)}.")
        if k == 5:
            return f"Masons began repairs on {rng.choice(PLACES)}, paid for by the {rng.choice(GUILDS)}."
        if k == 6:
            return (f"Merchants from {rng.choice(['Ostrel', 'the Sund Isles', 'Caravel Point', 'the inland duchies'])} "
                    f"brought {rng.choice(['amber', 'salt fish', 'dyed wool', 'iron bars', 'wine', 'spices'])} up the river.")
        if k == 7:
            return f"{person()} died at a great age and left a library to the Temple of the Tides."
        if k == 8:
            return f"The {rng.choice(GUILDS)}' Guild treasury {rng.choice(['gained', 'lost'])} {rng.randint(40, 900)} crowns that year."
        if k == 9:
            return f"Floods closed {rng.choice(['Barrow Bridge', 'Marrow Street', 'the Copper Docks', 'Marrowgate'])} for {rng.randint(2, 30)} days."
        return f"{person()} was fined {rng.randint(2, 50)} crowns for {rng.choice(['selling short measures', 'brawling at the quays', 'building without leave', 'dumping tannery waste in the river'])}."

    years = []
    size = 0
    year = 412
    while size < target_chars:
        sents = [sentence() for _ in range(rng.randint(3, 6))]
        years.append([year, sents])
        size += sum(len(s) + 1 for s in sents) + 12
        year += 1
    n = len(years)

    # counting: Marrow Bridge mentions (one sentence each, in distinct years) --------------------------------------
    mb_years = sorted(rng.sample(range(n), 37))
    for i in mb_years:
        s = rng.choice([f"Carts were weighed at the Marrow Bridge before entering the city.",
                        f"{person()} repaired the parapet of the Marrow Bridge.",
                        f"A ferry ran below the Marrow Bridge while its middle arch was rebuilt.",
                        f"The Marrow Bridge was hung with lanterns for the festival.",
                        f"Ice floes struck the Marrow Bridge but it held."])
        years[i][1].insert(rng.randrange(len(years[i][1]) + 1), s)
    mb_count = len(mb_years)

    # tracking: the city treasury --------------------------------------------------------------------------------
    treasury = 18400
    tr_years = sorted(rng.sample([i for i in range(n)], 70))
    recount = set(rng.sample(tr_years[10:-5], 3))
    for i in tr_years:
        if i in recount:
            treasury = max(0, treasury + rng.randint(-400, 400))
            s = f"A full recount found that the city treasury held exactly {treasury:,} crowns."
        else:
            r = rng.random()
            if r < 0.4 or treasury < 3000:
                x = rng.randint(30, 160) * 10
                treasury += x
                s = f"Taxes brought {x:,} crowns into the city treasury."
            elif r < 0.85:
                x = rng.randint(20, 120) * 10
                treasury -= x
                s = (f"The council spent {x:,} crowns from the city treasury on "
                     f"{rng.choice(['the Westwall', 'new barges', 'grain stores', 'the Lantern Tower roof', 'paving the Old Market'])}.")
            else:
                x = rng.randint(5, 60) * 10
                treasury -= x
                s = f"Thieves took {x:,} crowns from the city treasury vault and were never caught."
        years[i][1].append(s)
    tr_final = treasury

    # needles ---------------------------------------------------------------------------------------------------
    taken = set(mb_years) | set(tr_years)
    free = [i for i in range(n) if i not in taken]
    def spot(frac):
        target = int(frac * n)
        return min(free, key=lambda i: abs(i - target))
    needles = [
        (0.08, "The first great bell of the Lantern Tower was cast by the founder Oswin Thale, but it cracked in its first winter."),
        (0.21, "The great bell of the Lantern Tower that still rings today was cast by the founder Ysolde Marrek."),
        (0.30, "The river toll was set at five copper bits per barge."),
        (0.55, "The council raised the river toll to seven copper bits per barge, and it has stayed there since."),
        (0.36, "Before the fire, the Great Archive held 2,980 scrolls."),
        (0.62, "When the Great Archive reopened after the fire, it held 4,312 scrolls."),
        (0.44, "The harbour master's dog, Brindle, was famous on the quays."),
        (0.71, "The harbour master's cat, Pemberton, was given a collar of silver by the Bargemen."),
        (0.15, "The city's old motto was 'By Water and Salt'."),
        (0.86, "The council adopted a new motto for the city: 'Steady the Oar'."),
    ]
    for frac, s in needles:
        i = spot(frac)
        years[i][1].insert(rng.randrange(len(years[i][1]) + 1), s)
        free.remove(i)

    header = ("THE CHRONICLE OF VELMORA\nAs kept by the clerks of the Temple of the Tides, year by year. At the start "
              "of the year 412 the city treasury held 18,400 crowns.\n\n")
    body = "\n\n".join(f"In the year {y}: " + " ".join(s) for y, s in years)
    text = header + body + "\n\nHERE ENDS THE CHRONICLE\n"
    answers = {"needles": {"bell_founder": "Ysolde Marrek", "river_toll_copper_bits": "7",
                           "archive_scrolls_after_reopening": "4312", "harbour_master_cat": "Pemberton",
                           "current_motto": "Steady the Oar"},
               "count": mb_count, "track": tr_final}
    assert text.count("Marrow Bridge") == mb_count
    return text, answers


QUESTIONS = {
    "a": {
        "needles": ("From the log, report the current combination of the blue equipment locker, the archive number of "
                    "Dr. Okonkwo's ice core sample, the serial plate of the backup generator, the name of the supply "
                    "ship booked for the winter season, and the emergency radio frequency in MHz as it stands at the "
                    "end of the log. Reply with only a JSON object with exactly these keys: \"locker_combination\", "
                    "\"ice_core_archive\", \"generator_serial\", \"supply_ship\", \"radio_frequency_mhz\" (all values "
                    "as strings)."),
        "count": ("How many log entries (lines) mention snow petrels (singular or plural)? Count entries, not birds. "
                  "Give the final answer as the last line in the form `ANSWER: <integer>`."),
        "track": ("How many litres of fuel are in the main tank at the end of the log? Give the final answer as the "
                  "last line in the form `ANSWER: <integer>`."),
    },
    "b": {
        "needles": ("From the chronicle, report: who cast the great bell of the Lantern Tower that still rings today, "
                    "the river toll per barge in copper bits as it stands at the end of the chronicle, how many scrolls "
                    "the Great Archive held when it reopened after the fire, the name of the harbour master's cat, and "
                    "the city's motto at the end of the chronicle. Reply with only a JSON object with exactly these "
                    "keys: \"bell_founder\", \"river_toll_copper_bits\", \"archive_scrolls_after_reopening\", "
                    "\"harbour_master_cat\", \"current_motto\" (all values as strings)."),
        "count": ("How many times is the Marrow Bridge mentioned in the chronicle? (Marrowgate, Marrow Street and "
                  "Barrow Bridge are different places.) Give the final answer as the last line in the form "
                  "`ANSWER: <integer>`."),
        "track": ("How many crowns are in the city treasury at the end of the chronicle? Only the city treasury "
                  "counts, not guild treasuries. Give the final answer as the last line in the form "
                  "`ANSWER: <integer>`."),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-chars-a", type=int, default=293_000)
    ap.add_argument("--target-chars-b", type=int, default=344_000)
    a = ap.parse_args()
    (HERE / "docs").mkdir(exist_ok=True)
    out = []
    for key, fn, seed, tc in (("a", doc_a, 14014, a.target_chars_a), ("b", doc_b, 41041, a.target_chars_b)):
        text, ans = fn(random.Random(seed), tc)
        (HERE / "docs" / f"doc_{key}.txt").write_text(text, encoding="utf-8")
        for q in ("needles", "count", "track"):
            out.append({"id": f"l{key}_{q}", "doc": f"docs/doc_{key}.txt", "type": q, "question": QUESTIONS[key][q],
                        "answer": ans[q]})
        print(f"doc_{key}: {len(text):,} chars; count {ans['count']}, track {ans['track']}")
    (HERE / "questions.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
