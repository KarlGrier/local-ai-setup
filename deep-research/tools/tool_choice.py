"""tool_choice.py - one wording, used by both of Jan's MCP servers (research-mcp.py and web-mcp.py), for which tool a
question goes to (2026-10-19, the user's rule), so their descriptions never contradict each other."""

TOOL_CHOICE = ("Which tool: by default, answer with web_search, then fetch_page to read a result - also when a few "
               "sources need comparing. research_quick only when the user asks for quick research (\"quick research on "
               "...\"; about 1-3 minutes). research_start only when the user asks for deep research (it runs for hours). "
               "Never start either on your own.")   # the user, 2026-10-19: both research tools are ask-only

# 2026-10-19 (the user's rule): an earlier report is a starting point, not a source
PAST_REPORTS = ("An earlier research report (one this conversation did not just produce) is a starting point, not a "
                "source: say that you are using it and give its date. Anything in it that changes over time (models, "
                "prices, versions, rankings, availability, rules) is checked with a fresh web_search before you use it. "
                "In the answer, mark each point taken from it either as re-checked today or as carried over unchecked "
                "from the <date> report; never state an unchecked point as current fact. Call out what has changed "
                "since: \"your <date> report said X; now Y\".")

# 2026-10-19 (the user's rule): failed research must never look like research
RESEARCH_FAILED = ("When a research tool says FAILED, CANCELLED or NOT STARTED, that research produced nothing: stop asking "
                   "about that job, tell the user plainly that the answer was not researched and why, then answer with "
                   "web_search and fetch_page and say that this is what you did.")
