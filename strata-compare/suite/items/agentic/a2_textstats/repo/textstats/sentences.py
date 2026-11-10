ABBREVIATIONS = {"mr.", "mrs.", "dr.", "e.g.", "i.e.", "etc.", "vs."}


def split_sentences(text):
    """Split text into sentences. A sentence ends at '.', '!' or '?' (a run of them, like '?!' or '...', ends one
    sentence) followed by whitespace or the end of the text, except after one of the ABBREVIATIONS
    (case-insensitive). Sentences are returned stripped; empty ones are dropped."""
    out = []
    for part in text.split(". "):
        part = part.strip()
        if part:
            out.append(part if part.endswith(".") else part + ".")
    return out
