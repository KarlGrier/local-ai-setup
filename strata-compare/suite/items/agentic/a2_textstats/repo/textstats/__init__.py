"""Small text statistics."""
from .stats import summary
from .tokenize import words
from .sentences import split_sentences

__all__ = ["summary", "words", "split_sentences"]
