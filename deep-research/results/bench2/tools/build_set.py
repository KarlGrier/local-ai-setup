#!/usr/bin/env python3
"""build_set.py - write the frozen question sets and the answer file (2026-10-17 evening). Quotes are taken from the
pages saved by verify.py (sources/<sha1(url)[:12]>.txt)."""
import hashlib, json, re
from pathlib import Path
B = Path("/home/USER/ai/deep-research/results/bench2")
F = str(B / "files")

def quote(url, phrase, width=230):
    p = B / "sources" / (hashlib.sha1(url.encode()).hexdigest()[:12] + ".txt")
    t = p.read_text(errors="replace")
    i = t.lower().find(phrase.lower())
    assert i >= 0, (url, phrase)
    s = re.sub(r"\s+", " ", t[max(0, i - width // 2): i + width // 2]).strip()
    return {"url": url, "quote": "..." + s + "...", "saved": p.name}

W = "https://en.wikipedia.org/wiki/"
C = [
 # id, set, question, answer, accept, number, [(url, phrase), ...]
 ("c01", "screen", "The only goal of the 2026 FIFA World Cup final was scored in extra time. Which club did the goalscorer join in August 2026?",
  "Paris Saint-Germain", ["PSG", "Paris Saint Germain", "Paris SG"], None,
  [(W + "2026_FIFA_World_Cup_final", "Ferran Torres scored"), (W + "Ferran_Torres", "Paris Saint-Germain for a fee"),
   ("https://courthousenews.com/psg-bolsters-star-studded-attack-by-signing-world-cup-winner-ferran-torres-from-barcelona/", "Torres joins Paris Saint-Germain")]),
 ("c02", "screen", "The 2026 Nobel Prize in Physics went to a single scientist for work on a neutrino observatory at the South Pole. At which university was he based when the prize was awarded?",
  "University of Wisconsin–Madison", ["University of Wisconsin-Madison", "UW–Madison", "UW-Madison", "Wisconsin–Madison", "Wisconsin-Madison", "University of Wisconsin"], None,
  [("https://www.nobelprize.org/prizes/physics/2026/halzen/facts/", "University of Wisconsin"), (W + "Francis_Halzen", "University of Wisconsin")]),
 ("c03", "holdout", "One of the two 2026 Nobel laureates in Chemistry is Japanese. Which university was he affiliated with at the time of the award?",
  "Tokyo University of Science", [], None,
  [("https://www.nobelprize.org/prizes/chemistry/2026/soai/facts/", "Tokyo University of Science"), ("https://www.nippon.com/en/news/yjj2026100701005/", "Tokyo University of Science")]),
 ("c04", "holdout", "The 2026 Nobel Prize in Literature went to a writer who published a translation of an ancient Greek poet's fragments in 2002. Which poet?",
  "Sappho", [], None,
  [("https://www.nobelprize.org/prizes/literature/2026/summary/", "Anne Carson"), (W + "Anne_Carson", "awarded the Nobel Prize in Literature"), (W + "If_Not,_Winter", "Fragments of Sappho")]),
 ("c05", "screen", "Before she served as UN High Commissioner for Human Rights, the 2026 Nobel Peace Prize laureate was president of which international tribunal?",
  "International Criminal Tribunal for Rwanda", ["ICTR", "Tribunal for Rwanda"], None,
  [("https://www.nobelprize.org/prizes/peace/2026/summary/", "Navi Pillay"), (W + "Navi_Pillay", "president of the International Criminal Tribunal for Rwanda")]),
 ("c06", "holdout", "Which of the three 2026 Nobel laureates in Physiology or Medicine was affiliated with the University of Würzburg at the time of the award?",
  "Georg Nagel", ["Nagel"], None,
  [("https://www.nobelprize.org/prizes/medicine/2026/nagel/facts/", "University of Würzburg"), ("https://www.gpb.org/news/2026/10/05/nobel-medicine-prize-goes-3-scientists-for-research-brain-activity", "Nagel at the University of Würzburg")]),
 ("c07", "screen", "One of the two 2026 laureates of the economics prize in memory of Alfred Nobel wrote the textbook 'Interest and Prices'. Which university was he affiliated with at the time of the award?",
  "Columbia University", ["Columbia"], None,
  [("https://www.nobelprize.org/prizes/economic-sciences/2026/woodford/facts/", "Columbia University"), (W + "Michael_Woodford_(economist)", "teaches at Columbia University")]),
 ("c08", "holdout", "Which 2026 Fields Medalist holds positions at both New York University and France's IHES?",
  "Hong Wang", ["Wang Hong"], None,
  [("https://www.simonsfoundation.org/2026/07/23/2026-fields-medals-awarded-to-four-of-worlds-top-mathematicians/", "Hong Wang of New York University"),
   ("https://www.newswire.com/news/2026-fields-medals-awarded-to-four-of-worlds-top-mathematicians-22832507", "Hong Wang of New York University")]),
 ("c09", "screen", "Who directed the film that won the Golden Lion at the 2026 Venice Film Festival?",
  "May el-Toukhy", ["May el Toukhy", "el-Toukhy", "El Toukhy"], None,
  [("https://www.euronews.com/culture/2026/09/12/venice-film-festival-2026-woman-unknown-of-may-el-toukhy-wins-the-golden-lion", "Director May el-Toukhy"),
   ("https://www.avclub.com/venice-film-festival-winners-2026", "May el-Toukhy's Woman Unknown took the Golden Lion")]),
 ("c10", "holdout", "What is the title of the film that won the Grand Jury Prize (Silver Lion) at the 2026 Venice Film Festival?",
  "Possible Love", [], None,
  [("https://www.euronews.com/culture/2026/09/12/venice-film-festival-2026-woman-unknown-of-may-el-toukhy-wins-the-golden-lion", "Possible Love,” won the Silver Lion"),
   ("https://www.avclub.com/venice-film-festival-winners-2026", "Possible Love")]),
 ("c11", "screen", "Whom did the 2026 Wimbledon ladies' singles champion defeat in the final?",
  "Karolína Muchová", ["Muchova", "Karolina Muchova"], None,
  [(W + "2026_Wimbledon_Championships_–_Women's_singles", "Nosková defeated Karolína Muchová"),
   ("https://currentaffairs.adda247.com/wimbledon-championship-2026-full-list-of-winners-category-wise/", "Karolina Muchova in Wimbledon 2026 final")]),
 ("c12", "holdout", "The 2026 US Open men's singles champion had won his first Grand Slam title earlier in 2026. At which tournament?",
  "French Open", ["Roland Garros", "Roland-Garros"], None,
  [(W + "2026_US_Open_–_Men's_singles", "following the 2026 French Open"), ("https://www.drishtiias.com/state-pcs-current-affairs/alexander-zverev-wins-2026-us-open-title", "maiden Grand Slam title at Roland Garros")]),
 ("c13", "holdout", "In which round of the 2026 Open Championship at Royal Birkdale did the eventual champion shoot a 62?",
  "third round", ["third", "round 3", "3rd round", "Saturday"], None,
  [(W + "2026_Open_Championship", "Fox, who went out early during the third round, shot an eight under round of 62"),
   ("https://pluggedingolf.com/2026-the-open-championship-recap/", "on Saturday with a 62")]),
 ("c14", "screen", "The runner-up of the 2026 Tour de France won his first Tour mountain stage that year. At which summit finish?",
  "Plateau de Solaison", ["Solaison"], None,
  [(W + "2026_Tour_de_France", "Evenepoel took his first mountain stage victory at Plateau de Solaison"),
   ("https://www.topendsports.com/events/tour-de-france/tours/2026.htm", "Plateau de Solaison 184 km Remco Evenepoel")]),
 ("c15", "holdout", "How many gold medals did China win at the 2026 Asian Games in Aichi-Nagoya?",
  "169 gold", ["169 golds", "169 gold medals"], None,
  [("https://www.koreatimes.co.kr/sports/20261004/20th-asian-games-draw-to-conclusion-with-celebration-of-athletic-feats", "China won 169 gold medals"),
   ("https://www.onmanorama.com/sports/other-sports/2026/10/04/asian-games-officially-conclude-india-cherish-fourth-place-finish.html", "including 169 golds")]),
 ("c16", "screen", "From which grid position did the winner of the 2026 Italian Grand Prix at Monza start the race?",
  "19th", ["P19", "nineteenth", "19th on the grid", "19th place"], None,
  [("https://api.fia.com/news/f1-antonelli-storms-19th-grid-take-sensational-home-win-monza-ahead-russell-and-verstappen", "Antonelli storms from 19th on the grid"),
   ("https://www.silverstone.co.uk/news/f1-2026-italian-grand-prix-results-antonelli-wins-19th-monza", "Antonelli wins from 19th at Monza")]),
 ("c17", "screen", "The 2026 Booker Prize shortlist includes a novel by the author who won the prize in 2020. What is that novel's title?",
  "John of John", [], None,
  [("https://thebookerprizes.com/media-centre/press-releases/shocking-understated-discomfiting-hilarious-shortlist-for-booker-prize", "John of John by Douglas Stuart"),
   ("https://www.businessday.co.za/lifestyle/books/2026-10-01-booker-prize-shortlist-spans-kingston-to-the-hebrides/", "Douglas Stuart, who won in 2020")]),
 ("c18", "holdout", "How many goals did the winner of the 2026 FIFA World Cup Golden Boot score at the tournament?",
  "10 goals", ["ten goals"], None,
  [("https://www.nbcsports.com/soccer/news/2026-world-cup-award-winners-golden-boot-golden-ball-best-young-player-golden-glove", "scoring 10 goals"),
   ("https://allafrica.com/stories/202607210766.html", "scoring 10 goals in eight matches")]),
 ("c19", "holdout", "Which club does the player named Best Young Player of the 2026 FIFA World Cup play for?",
  "Barcelona", ["FC Barcelona", "Barça"], None,
  [(W + "Pau_Cubarsí", "named the tournament's Best Young Player"), (W + "Pau_Cubarsí", "La Liga club Barcelona"),
   ("https://www.nbcsports.com/soccer/news/2026-world-cup-award-winners-golden-boot-golden-ball-best-young-player-golden-glove", "Cubars")]),
 ("c20", "screen", "For which series did the winner of the 2026 Primetime Emmy for Outstanding Lead Actress in a Drama Series win?",
  "Pluribus", [], None,
  [("https://www.tvinsider.com/1286050/emmys-2026-winners-full-list/", "Rhea Seehorn , Pluribus — WINNER"),
   ("https://abc11.com/story/emmys-2026-full-list-winners-nominees-78th-primetime-emmy-awards/19831393/", "Rhea Seehorn, \"Pluribus\" -- WINNER")]),
 ("c21", "holdout", "How many Emmy awards in total did the series that won Outstanding Comedy Series at the 2026 Primetime Emmys receive, a record for a comedy?",
  "14 awards", ["14 Emmys", "14 Emmy", "fourteen"], None,
  [("https://abc11.com/story/emmys-2026-full-list-winners-nominees-78th-primetime-emmy-awards/19831393/", "breaking a record for a comedy series with 14 awards"),
   ("https://blueprint.ng/?p=844866", "record 14 awards")]),
 ("c22", "screen", "How many Riksdag seats did the largest party win in Sweden's September 2026 general election?",
  "99 seats", [], None,
  [(W + "2026_Swedish_general_election", "28.0% of the vote and 99 seats"),
   ("https://www.cp24.com/news/world/2026/09/17/swedens-prime-minister-kristersson-to-resign-after-left-leaning-opposition-narrowly-wins-election/", "biggest single party with 99 seats")]),
 ("c23", "holdout", "Who was the lead candidate of the party that won the September 2026 Berlin state election?",
  "Elif Eralp", ["Eralp"], None,
  [(W + "2026_Berlin_state_election", "Left lead candidate Elif Eralp"),
   ("https://www.bluewin.ch/en/news/the-left-wins-the-berlin-election-by-a-wide-margin-li.3607064", "Elif Eralp (The Left), the party’s top candidate")]),
 ("c24", "screen", "Which candidate finished third in the first round of Brazil's October 2026 presidential election?",
  "Augusto Cury", ["Cury"], None,
  [("https://www.thestar.com.my/news/world/2026/10/09/third-place-finisher-in-brazil-election-endorses-bolsonaro-for-runoff-against-lula", "received 2.89%"),
   ("https://viva.com.br/eleicoes2026", "Augusto Cury (AVANTE) 2,89 %")]),
 ("c25", "screen", "Python 3.15.0 needed a surprise third release candidate shortly before its October 2026 release. Release blockers in which feature caused it?",
  "lazy imports", ["lazy import", "lazy-import"], None,
  [("https://www.python.org/downloads/release/python-3150rc3/", "last-minute lazy-import release blockers"),
   ("https://realpython.com/python-news-october-2026/", "last-minute bugs in lazy imports forced a surprise third release candidate")]),
 ("c26", "holdout", "Which mainline Linux kernel version does Ubuntu 26.10 'Stonking Stingray' ship with?",
  "7.3", ["Linux 7.3", "kernel 7.3"], None,
  [("https://www.omgubuntu.co.uk/2026/09/ubuntu-2610-kernel-version", "switched its target from Linux 7.2 to Linux 7.3"),
   ("https://ubuntuhandbook.org/index.php/2026/10/ubuntu-26-10-released-with-kernel-7-3-gnome-51-amd64v3-image/", "Released with Kernel 7.3")]),
 ("c27", "screen", "On the 2026 Starship test flight that reached orbit for the first time, how many Starlink satellites were deployed?",
  "26 Starlink", ["26 next-generation", "26 V3", "26 satellites", "26 operational"], None,
  [("https://www.euronews.com/2026/09/28/spacexs-starship-reaches-orbit-for-the-first-time", "deployed 26 next-generation Starlink satellites"),
   (W + "Starship_flight_test_14", "deployed 26 operational Starlink V3 satellites")]),
 ("c28", "holdout", "What headline value was reported for NVIDIA's agreement to acquire Hugging Face, announced in September 2026?",
  "$12.9 billion", ["12.9 billion", "12.93 billion", "$12.9B", "12.9B", "12.9 bn", "12.9bn"], {"value": 12.9, "tol": 0.05},
  [("https://semafor.com/article/09/03/2026/nvidia-to-buy-hugging-face-for-nearly-13-billion", "for $12.9 billion"),
   ("https://unite.ai/nvidia-signs-definitive-agreement-to-acquire-hugging-face-for-12-9b", "Acquire Hugging Face for $12.9B")]),
 ("c29", "screen", "According to its technical report, how many parameters are active per token in Moonshot AI's Kimi K3 model?",
  "104 billion", ["104B", "104 B", "104 billion"], None,
  [("https://pasqualepillitteri.it/en/news/9007/kimi-k3-open-weights-technical-report", "the active parameters per token are 104 billion"),
   ("https://aiweekly.co/alerts/moonshot-open-sources-kimi-k3-a-28t-parameter-moe-model", "104 billion active per token")]),
 ("c30", "holdout", "The first hurricane of the 2026 Atlantic season formed later in the year than in almost any season on record. Near which Florida city did it make landfall?",
  "Destin", [], None,
  [(W + "2026_Atlantic_hurricane_season", "Isaias made landfall near Destin"),
   ("https://www.newsweek.com/hurricane-isaias-live-path-tracker-updates-where-storm-us-landfall-12545078", "made landfall near Destin")]),
]
O = [
 ("o01", "screen", "What is new in 2025-2026 in running mixture-of-experts LLMs with the experts kept in system RAM on consumer GPUs that my Strata project (attached: its REPORT.md and NOTES.md) has not tried yet? For each technique: where it is implemented, how mature it is, and what trying it on my PC (RTX 5080 16 GB + RTX 4060 Ti 16 GB, 96 GB DDR5) would take. Say plainly where nothing new was found.",
  [F + "/strata-REPORT.md", F + "/strata-NOTES.md"]),
 ("o02", "screen", "Which 16 GB graphics card should I add as a third GPU to a PC with an RTX 5080 and an RTX 4060 Ti (96 GB RAM) to run large local LLMs (mixture-of-experts, experts partly in RAM) faster? Compare the options available in the US in October 2026: price, where to buy, memory bandwidth, PCIe link, power and physical fit, and the trade-offs.", []),
 ("o03", "screen", "What changed during 2026 in the EU AI Act's obligations for providers of general-purpose AI models and of high-risk AI systems, including the Digital Omnibus proposals, and what applies as of October 2026?", []),
 ("o04", "holdout", "Which open-source projects in 2025-2026 run large mixture-of-experts LLMs on consumer hardware by keeping the experts in system RAM or on SSD, how do their techniques and measured speeds compare, and which are actively maintained?", []),
 ("o05", "holdout", "What is confirmed, as opposed to rumored, about Qwen4 Flash as of October 2026: release status and date, architecture (total and active parameters, experts, context length), license, benchmark results, and availability (weights, quantizations, hosted APIs)?", []),
 ("o06", "holdout", "Which uninterruptible power supply (UPS) should I buy in the US for a home AI workstation drawing about 900 W at peak: pure sine wave output, enough runtime at 600 W to shut down cleanly, quiet, and supported on Linux (NUT)? Compare models available in October 2026 with prices, where to buy, and the trade-offs.", []),
]
qs = {"screen": [], "holdout": []}
answers = []
for cid, st, q, a, acc, num, srcs in C:
    qs[st].append({"id": cid, "kind": "checkable", "question": q, "files": []})
    rec = {"id": cid, "set": st, "answer": a, "accept": acc, "sources": [quote(u, ph) for u, ph in srcs]}
    if num:
        rec["number"] = num
    answers.append(rec)
for oid, st, q, files in O:
    qs[st].append({"id": oid, "kind": "open", "question": q, "files": files})
for st, rows in qs.items():
    (B / f"questions-{st}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
(B / "answers" / "answers.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in answers))
print({k: len(v) for k, v in qs.items()}, len(answers), "answers")
