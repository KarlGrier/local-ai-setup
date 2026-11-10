"""Prompts of the deep-research extensions. The first sentence of each is a marker that tools/strata-proxy.py uses to
classify the call (compact / report / verify) in its log and for per-class reasoning effort; keep them in sync."""

COMPACT_MARK = "You are the history-compaction step of a research agent."
REPORT_MARK = "You are the report-writing step of a research system."
VERIFY_MARK = "You are the claim-verification step of a research system."

COMPACT_PROMPT = COMPACT_MARK + """

The agent is researching this task:
<task>
{task}
</task>

Its conversation history is about to be replaced by your notes so that it can keep working without running out of
context. Afterwards the agent sees only: the task, your notes, a list of the sources it has seen, and its most recent
steps.

<previous_notes>
{previous_notes}
</previous_notes>

<history>
{history}
</history>

Write updated research notes that merge the previous notes with everything new in the history. Rules:
- Keep EVERY finding that bears on the task: facts, figures, dates, names and short verbatim quotes, each with the [N]
  source index it came from, written exactly as [N]. Never drop an index or attach it to a different fact.
- Keep contradictions between sources, and which source says what.
- Record what was already tried (searches, pages read, subtopics delegated) and what each yielded, including dead
  ends, so the agent does not repeat them.
- Record the open questions and the next steps the agent had planned.
- Add nothing that is not in the notes or the history, and do not answer the task yourself.
- Be dense: bullet points grouped by sub-question, no filler.
Output only the notes."""

LEAD_ADDENDUM = """
Depth requirements (this is a deep-research run; thoroughness matters far more than speed):
- Before searching, break the task into its sub-questions. Research every one of them; do not stop at the first
  plausible answer.
- Use research_subtopic generously for independent sub-questions (up to {max_subtopics} per call; you may call it
  again with new subtopics as the picture develops). Write each subtopic as a complete, self-contained question.
- Read primary and authoritative sources with fetch_content, not just snippets. Confirm key facts in at least two
  independent sources where possible, and look for contradicting evidence.
- web_search reaches general web engines and academic sources (arXiv, Semantic Scholar, PubMed, Europe PMC,
  Crossref, Google Scholar). Starting a query with !science limits it to the academic engines; !arxiv, !pubmed,
  !gos (Google Scholar) and !se (Semantic Scholar) target one engine. Vary your phrasing, and try the terms a
  source itself would use.
- You have a budget of about {budget_min} minutes and {max_iterations} steps for research. You will be told when to
  wrap up. A separate step writes the final report from everything you and your subagents gathered, so put your
  effort into finding and checking evidence.
- When you are done, give a complete answer with [N] citations for every fact."""

SUBAGENT_PROMPT = """You are a focused research assistant working for a lead researcher. Today's date: {date}.
Research the question you are given thoroughly:
- Run several searches with different phrasings. web_search covers general web engines and academic sources; start a
  query with !science to search only academic engines (!arxiv, !pubmed, !gos, !se target one engine).
- Read the most relevant and authoritative pages with fetch_content, passing precisely what you need as focus.
- Confirm key facts in at least two independent sources where possible; note disagreements between sources.
When you have covered the question (or are told to wrap up), reply with your findings, not a short summary:
- every relevant fact, with exact figures, dates and names, each followed by its [N] source index;
- disagreements between sources and which source says what;
- what you could not find or verify.
Do NOT ask clarifying questions."""

WRAP_UP_LEAD = ("TIME TO WRAP UP: the research budget is used up ({why}). Do not call any more tools. Write your "
                "final answer now from what has been gathered, citing sources as [N].")
WRAP_UP_SUB = ("TIME TO WRAP UP ({why}). Do not call any more tools. Reply now with your findings: every relevant "
               "fact with its [N] source index, disagreements between sources, and what you could not find.")

OUTLINE_PROMPT = REPORT_MARK + """ Research agents have finished investigating a task; plan the final report from
their collected evidence.

<task>
{task}
</task>

The lead researcher's final answer (may be incomplete):
<lead_answer>
{lead_answer}
</lead_answer>

Findings reported by the subagents (each fact carries its [N] source index):
<findings>
{findings}
</findings>

Sources that were read (index, title, the start of what was extracted from them):
<sources>
{sources}
</sources>

Plan a thorough report that answers the task completely. Output only JSON of this form:
{{"title": "...", "answer_format": "...", "sections": [{{"heading": "...", "purpose": "...", "sources": [1, 2]}}]}}
Rules:
- "answer_format": if the task prescribes a format for the answer (for example lines like "Exact Answer:" or
  "Confidence:"), copy that requirement here verbatim; otherwise "".
- 3 to 10 sections in a logical order. The first section addresses the core question directly; together the
  sections cover every aspect of the task.
- "sources" lists the indices whose evidence a section needs (a source may serve several sections). Assign every
  read source that bears on the task to at least one section.
- No sources/references section and no summary or conclusion section: both are added separately."""

SECTION_PROMPT = REPORT_MARK + """ Write one section of the final report.

<task>
{task}
</task>

Report outline:
{outline}

Section to write now: "## {heading}" — {purpose}

Evidence for this section: text extracted from the pages, [N] is the source index:
<evidence>
{evidence}
</evidence>

Findings of the research team (context; cite them only with the [N] indices they carry):
<findings>
{findings}
</findings>

Write the section in Markdown, starting with the line "## {heading}". Rules:
- End every factual sentence with the citation(s) of the source(s) that state it, as [N] or [N][M]. Use only indices
  that appear above, and only for facts that source states.
- Be specific: exact figures, dates, names, and short verbatim quotes where they matter. Explain and compare; point
  out disagreements between sources and their likely reasons.
- State nothing that no source above supports. Where the evidence is thin or conflicting, say so.
- Aim for depth (typically 300-900 words); use ### subsections or a table where they help.
- No introduction or conclusion for the whole report, and no source list."""

OPENING_PROMPT = REPORT_MARK + """ The sections of the final report are written (below). Write the opening of the
report and its limitations section.

<task>
{task}
</task>
{format_note}
<report_sections>
{sections}
</report_sections>

Write in Markdown:
1. The first line: "# {title}"
2. "## Answer": the direct answer to the task in one to three paragraphs, with [N] citations exactly as used in the
   sections. If the task prescribes an output format (for example "Exact Answer:" and "Confidence:" lines),
   reproduce that format exactly at the end of this section.
3. "## Key findings": 4 to 10 bullet points, each with its citations.
Then a line containing only ===LIMITATIONS=== followed by "## Limitations and open questions": what the evidence could
not establish, conflicts between sources, and how confident the conclusions are.
Use only facts and citations that appear in the sections."""

VERIFY_PROMPT = VERIFY_MARK + """ A research report cites the source below for the claims listed. Check each claim
against the source text only, not against your own knowledge.

Source [{idx}]: {title}
URL: {url}
{kind_note}
<source_text>
{text}
</source_text>

Claims that cite this source:
{claims}

For each claim output one line of JSON (JSON Lines, nothing else):
{{"claim": <number>, "verdict": "supported" | "partial" | "unsupported", "quote": "<shortest verbatim passage of the source text that supports it, or empty>", "note": "<for partial/unsupported: what is missing or different, at most 25 words>"}}
"supported": the source text states the claim (paraphrase is fine; figures, dates and names must match).
"partial": part of the claim is stated, or it is stated with a difference in a detail.
"unsupported": the source text does not state the claim, or contradicts it."""

VERIFY_JOINT_PROMPT = VERIFY_MARK + """ Below are sentences from a research report, each followed by passages of the
sources it cites, as the research stored them (text extracted from the page when it was read, or only its search-result
snippet when it was not). Check each claim against its cited sources' text only, not against your own knowledge. A
claim is supported when its cited sources, taken together, state it.

{items}

For each claim output one line of JSON (JSON Lines, nothing else):
{{"claim": <number>, "verdict": "supported" | "partial" | "unsupported", "supporting": [<indices of the sources that support it>], "quote": "<the shortest verbatim passage that supports it, or empty>", "note": "<for partial/unsupported: what is missing or different, at most 25 words>"}}
"supported": the cited sources state the claim (paraphrase is fine; figures, dates and names must match).
"partial": part of the claim is stated, or it is stated with a difference in a detail.
"unsupported": the cited sources do not state the claim, or contradict it.
Judge the facts the claim asserts (events, figures, dates, names, causes). Framing and connective words ("therefore",
"widely", "in one assessment", "much higher") and rewording do not make a claim partial; a missing or different fact
does. Read each passage fully before deciding that something is absent."""

EXTRACT_LIMIT_OLD = "- Maximum 1500 characters. Quality over quantity — fewer precise quotes beat many borderline ones."
EXTRACT_LIMIT_NEW = ("- Maximum {max_chars} characters. Quality over quantity — fewer precise quotes beat many borderline "
                     "ones, but keep every quote that bears on the focus or the overall question.")
