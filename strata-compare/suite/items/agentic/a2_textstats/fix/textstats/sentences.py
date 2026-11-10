import re

ABBREVIATIONS = {"mr.", "mrs.", "dr.", "e.g.", "i.e.", "etc.", "vs."}


def split_sentences(text):
    """Split text into sentences. A sentence ends at '.', '!' or '?' (a run of them, like '?!' or '...', ends one
    sentence) followed by whitespace or the end of the text, except after one of the ABBREVIATIONS
    (case-insensitive). Sentences are returned stripped; empty ones are dropped."""
    out, start = [], 0
    for m in re.finditer(r"[.!?]+(?=\s|$)", text):
        end = m.end()
        last_word = text[start:end].split()[-1].lower() if text[start:end].split() else ""
        if last_word in ABBREVIATIONS:
            continue
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        start = end
    rest = text[start:].strip()
    if rest:
        out.append(rest)
    return out
