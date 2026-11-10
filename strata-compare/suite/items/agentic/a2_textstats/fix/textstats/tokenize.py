import re

def words(text):
    """Lowercased words: runs of letters, digits and apostrophes inside a word (don't, rock'n'roll).
    Apostrophes at the start or end of a run are not part of the word. Everything else separates words.
    Letters include accented ones (café is one word)."""
    out = []
    for m in re.finditer(r"[^\W_']+(?:'+[^\W_']+)*", text):
        out.append(m.group(0).lower())
    return out
