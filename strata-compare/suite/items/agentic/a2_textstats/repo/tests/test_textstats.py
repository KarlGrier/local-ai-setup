import unittest

from textstats import split_sentences, summary, words


class Words(unittest.TestCase):
    def test_punctuation_and_case(self):
        self.assertEqual(words("Hello, world! Hello again."), ["hello", "world", "hello", "again"])

    def test_apostrophes(self):
        self.assertEqual(words("Don't 'quote' me"), ["don't", "quote", "me"])

    def test_whitespace_and_accents(self):
        self.assertEqual(words("café\tau  lait\n2 cups"), ["café", "au", "lait", "2", "cups"])


class Sentences(unittest.TestCase):
    def test_marks(self):
        self.assertEqual(split_sentences("Is it? Yes! It is."), ["Is it?", "Yes!", "It is."])

    def test_abbreviations(self):
        self.assertEqual(split_sentences("Dr. Smith met Mr. Jones. They talked."),
                         ["Dr. Smith met Mr. Jones.", "They talked."])

    def test_runs(self):
        self.assertEqual(split_sentences("Wait... What?! Fine"), ["Wait...", "What?!", "Fine"])


class Summary(unittest.TestCase):
    def test_summary(self):
        s = summary("The cat sat. The dog sat too! A bird?")
        self.assertEqual(s["words"], 9)
        self.assertEqual(s["sentences"], 3)
        self.assertEqual(s["avg_sentence_length"], 3.0)
        self.assertEqual(s["top3"], [["sat", 2], ["the", 2], ["a", 1]])

    def test_empty(self):
        self.assertEqual(summary(""), {"words": 0, "unique_words": 0, "sentences": 0, "avg_sentence_length": 0.0,
                                       "top3": []})


if __name__ == "__main__":
    unittest.main()
