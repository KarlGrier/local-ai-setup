from collections import Counter

from .sentences import split_sentences
from .tokenize import words


def summary(text):
    """{'words': n, 'unique_words': n, 'sentences': n, 'avg_sentence_length': words per sentence rounded to 2
    decimals (0.0 when there are no sentences), 'top3': the 3 most common words as [word, count] pairs, most common
    first, ties broken alphabetically}"""
    ws = words(text)
    ss = split_sentences(text)
    top = Counter(ws).most_common(3)
    return {
        "words": len(ws),
        "unique_words": len(set(ws)),
        "sentences": len(ss),
        "avg_sentence_length": round(len(ws) / len(ss), 2),
        "top3": [[w, c] for w, c in top],
    }
