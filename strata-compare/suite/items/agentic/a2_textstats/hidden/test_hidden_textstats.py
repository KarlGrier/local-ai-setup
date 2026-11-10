import unittest

from textstats import split_sentences, summary, words


class HiddenTextstats(unittest.TestCase):
    def test_words_more(self):
        self.assertEqual(words("rock'n'roll -- e-mail; ''x'' 3.5"), ["rock'n'roll", "e", "mail", "x", "3", "5"])
        self.assertEqual(words("ÉCOLE Über naïve"), ["école", "über", "naïve"])
        self.assertEqual(words(""), [])

    def test_sentences_more(self):
        self.assertEqual(split_sentences("See e.g. the docs. Done"), ["See e.g. the docs.", "Done"])
        self.assertEqual(split_sentences("DR. Who? No."), ["DR. Who?", "No."])
        self.assertEqual(split_sentences("Version 3.5 is out. Great"), ["Version 3.5 is out.", "Great"])
        self.assertEqual(split_sentences("  \n "), [])

    def test_summary_more(self):
        s = summary("b a. a b. c!")
        self.assertEqual(s["top3"], [["a", 2], ["b", 2], ["c", 1]])
        self.assertEqual(s["avg_sentence_length"], 1.67)
        self.assertEqual(s["unique_words"], 3)


if __name__ == "__main__":
    unittest.main()
