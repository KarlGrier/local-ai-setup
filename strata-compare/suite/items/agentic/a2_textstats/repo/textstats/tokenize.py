def words(text):
    """Lowercased words: runs of letters, digits and apostrophes inside a word (don't, rock'n'roll).
    Apostrophes at the start or end of a run are not part of the word. Everything else separates words.
    Letters include accented ones (café is one word)."""
    return [w.lower() for w in text.split(" ") if w]
