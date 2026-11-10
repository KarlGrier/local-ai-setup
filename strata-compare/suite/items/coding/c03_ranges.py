LEVEL = "easy"
KIND = "algorithms"
ENTRY = "summarize_ranges"
PROMPT = """Write a Python function `summarize_ranges(nums: list[int]) -> str`.

The input is a list of integers in any order, possibly with duplicates. Take the distinct values in increasing order and split them into maximal runs of consecutive integers. Write each run as:
- `a..b` if the run has 3 or more values (from a to b),
- `a,b` if it has exactly 2 values,
- `a` if it has 1 value.
Join the pieces with "," (no spaces). An empty list gives "".

Examples: [5, 1, 2, 3, 7, 8, 10] -> "1..3,5,7,8,10"; [-3, -2, -1, 1] -> "-3..-1,1".
"""

GOOD = r'''
def summarize_ranges(nums):
    vals = sorted(set(nums))
    out = []
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[j] + 1:
            j += 1
        n = j - i + 1
        if n >= 3:
            out.append(f"{vals[i]}..{vals[j]}")
        elif n == 2:
            out.append(f"{vals[i]},{vals[j]}")
        else:
            out.append(str(vals[i]))
        i = j + 1
    return ",".join(out)
'''

BAD = r'''
def summarize_ranges(nums):
    vals = sorted(set(nums))
    out = []
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[j] + 1:
            j += 1
        out.append(f"{vals[i]}..{vals[j]}" if j > i else str(vals[i]))
        i = j + 1
    return ",".join(out)
'''

# ==== HIDDEN TESTS ====
def test_examples(sol):
    assert sol.summarize_ranges([5, 1, 2, 3, 7, 8, 10]) == "1..3,5,7,8,10"
    assert sol.summarize_ranges([-3, -2, -1, 1]) == "-3..-1,1"


def test_empty_and_single(sol):
    assert sol.summarize_ranges([]) == ""
    assert sol.summarize_ranges([4]) == "4"
    assert sol.summarize_ranges([4, 4, 4]) == "4"


def test_pairs(sol):
    assert sol.summarize_ranges([2, 1]) == "1,2"
    assert sol.summarize_ranges([0, -1, 5, 6, 9]) == "-1,0,5,6,9"


def test_duplicates(sol):
    assert sol.summarize_ranges([3, 1, 2, 2, 3, 1, 9, 9, 10, 11]) == "1..3,9..11"


def test_big(sol):
    nums = list(range(-1000, 1000)) + [5000, 5001, 7000]
    assert sol.summarize_ranges(nums[::-1]) == "-1000..999,5000,5001,7000"


def test_negative_runs(sol):
    assert sol.summarize_ranges([-10, -9, -8, -6, -5, -3]) == "-10..-8,-6,-5,-3"
