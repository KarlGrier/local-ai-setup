# Phase 5: harder checkable questions - proposal for Karl (2026-10-28; NOT frozen until Karl approves)

**Why:** the checkable sets are saturated. Pristine LDR (the baseline) got hard screen 10/10 and screen 15/15; every
phase 4 arm got 5/5 on the hard five. The holdout's 25 checkable questions were built the same way: the answer only had
to be absent from the top-10 snippets of ONE plain search. So they will not separate setups.

**How these were built:** recent (Aug 15 - Oct 25, 2026); hard by structure (two hops, an aggregate across sources,
or a prominent wrong/provisional answer); the answer absent from the top-10 SearXNG snippets of THREE queries (the
question + 2 rephrasings); each hop on 2+ independent sources, one primary. Built by one agent (8 candidates, 4 kept, 5
rejected on snippet hits, incl. one reworded); verified by a second agent that answered each one itself from primary
sources BEFORE reading the key (all 4 agree), checked the wording for second readings, and checked stability to
11-10. Details: candidates.md (builder + "Verification" section).

| id | question (final wording) | answer (accept) | distractors | type |
|---|---|---|---|---|
| p5c1b | In the October 5, 2026 Quebec general election, how many seats did the party that became the Official Opposition hold once all judicial recounts were completed? | 39 ("39", "thirty-nine") | 40 (election night; still in Élections Québec's snippet) | two hops + provisional figure |
| p5c2 | In the full rankings published in the official 2026 Hugo Award voting statistics, which novel was placed second in the Best Novel category? | The Incandescent | The Raven Scholar (lost the winner's final round, officially 4th); Death of the Author (2nd-most first preferences) | provisional-looking order + reading the stats |
| p5c5 | Among JPMorgan Chase, Bank of America, Citigroup and Wells Fargo, what was the lowest CET1 ratio under the Standardized approach reported for 30 September 2026 in their Q3 2026 earnings releases? | 10.0% (Wells Fargo) ("10.0%", "10.0 %") | 11.8% (WFC Advanced), 10.9% (BofA) | aggregate over 4 filings |
| p5c6 | Which university did the top points scorer for the losing team at the 2026 Solheim Cup play college golf for? | UCLA ("UCLA", "University of California, Los Angeles") | University of Virginia (Coughlin, 3.5 pts) | two hops (easiest) |

Verified numbers: CET1 Standardized / Advanced at 9/30/26 - JPM 13.9 / 14.1, BofA 10.9 / 12.0, Citi 12.8 / 12.0,
WFC 10.0 / 11.8. Quebec seats on 10-28 (Assemblée nationale): PQ 60, Liberal 39, Conservative 19, QS 9; the only
recounts (Vachon, Champlain) ended by 10-22; no court filing. Solheim Cup: Alison Lee 4-0-0, unique US top scorer.

**Proposed with them:**
1. **Grading rule for these (and better for all checkable questions):** correct only if the "## Answer" section
   commits to the key's answer; naming a distractor as the answer, or hedging between it and the key, is wrong. The
   short answers "39" and "10.0%" are too common for a whole-report string match, so these are graded on the Answer
   section (blind, by me or a fresh grader), not by the script.
2. **A difficulty pilot** (about 1 h of GPU): one quick-profile run per question. A question the quick profile gets
   right with no hesitation is dropped. The quick profile is not one of the Phase 5 arms, so the pick does not favour
   either of them.
3. **How many:** these 4 replace nothing; they are added to the holdout's checkable part (25 + 4). Or keep only the
   4 + the open questions as the deciding checkable set, if you prefer a smaller, sharper Phase 5.
