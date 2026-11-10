"""Independent brute-force / exact computations of every math answer.  The self-test checks that each stored
answer in problems.json equals what these functions compute."""
from fractions import Fraction
from itertools import combinations, product
from math import gcd, isqrt


def m01():   # ordered pairs a <= b with 1/a + 1/b = 1/360
    n, c = 360, 0
    for a in range(n + 1, 2 * n + 1):
        if (n * a) % (a - n) == 0 and n * a // (a - n) >= a:
            c += 1
    return c


def m02():   # 1..5000 expressible as x^2 - y^2 with x, y >= 0
    vals = set()
    for x in range(0, 2600):
        for y in range(0, x + 1):
            d = x * x - y * y
            if 1 <= d <= 5000:
                vals.add(d)
    return len(vals)


def m03():   # n <= 3000 with digit sum of n == digit sum of 7n
    ds = lambda k: sum(map(int, str(k)))
    return sum(1 for n in range(1, 3001) if ds(n) == ds(7 * n))


def m04():   # jumps +1/+2 from 0 to 19, never landing on a multiple of 4 (after the start)
    ways = [0] * 20
    ways[0] = 1
    for k in range(1, 20):
        if k % 4 == 0:
            continue
        ways[k] = ways[k - 1] + (ways[k - 2] if k >= 2 else 0)
    return ways[19]


def m05():   # two 10-sided dice: P(product is a perfect square) = m/n, answer m + n
    good = sum(1 for a in range(1, 11) for b in range(1, 11) if isqrt(a * b) ** 2 == a * b)
    f = Fraction(good, 100)
    return f.numerator + f.denominator


def m06():   # lattice points strictly inside x^2 + y^2 = 250
    return sum(1 for x in range(-16, 17) for y in range(-16, 17) if x * x + y * y < 250)


def m07():   # (3^2026 + 7^2026) mod 1000
    return (pow(3, 2026, 1000) + pow(7, 2026, 1000)) % 1000


def m08():   # numbers whose digits strictly increase, adjacent digits differ by >= 2, divisible by 3, at least 2 digits
    c = 0
    for k in range(2, 10):
        for digs in combinations(range(1, 10), k):
            if all(digs[i + 1] - digs[i] >= 2 for i in range(k - 1)) and sum(digs) % 3 == 0:
                c += 1
    return c


def m09():   # sum_{k=1}^{2026} floor(k^2 / 2027)
    return sum(k * k // 2027 for k in range(1, 2027))


def m10():   # tilings of a 3 x 9 board by 1 x 3 straight trominoes
    from functools import lru_cache
    W, H = 9, 3

    @lru_cache(None)
    def f(filled):           # filled: frozenset of cells, fill the first empty cell (row-major)
        cells = [(r, c) for c in range(W) for r in range(H)]
        for cell in cells:
            if cell not in filled:
                break
        else:
            return 1
        r, c = cell
        total = 0
        horiz = [(r, c + i) for i in range(3)]
        vert = [(r + i, c) for i in range(3)]
        for piece in (horiz, vert):
            if all(0 <= pr < H and 0 <= pc < W and (pr, pc) not in filled for pr, pc in piece):
                total += f(filled | frozenset(piece))
        return total

    return f(frozenset())


def m11():   # smallest n with exactly 1000 trailing zeros in n! ... none -> smallest n with >= 1000
    def z(n):
        s, p = 0, 5
        while p <= n:
            s += n // p
            p *= 5
        return s
    n = 1
    while z(n) < 1003:
        n += 1
    return n if z(n) == 1003 else -1


def m12():   # subsets of {1..16} (incl. empty) with sum divisible by 5
    cnt = [0] * 5
    cnt[0] = 1
    for k in range(1, 17):
        new = cnt[:]
        for r in range(5):
            new[(r + k) % 5] += cnt[r]
        cnt = new
    return cnt[0]


def m13():   # triangle 25-39-56: altitude to the side of length 56
    a, b, c = 25, 39, 56
    s = Fraction(a + b + c, 2)
    area2 = s * (s - a) * (s - b) * (s - c)
    area = Fraction(isqrt(area2.numerator), isqrt(area2.denominator))
    assert area * area == area2
    h = 2 * area / 56
    assert h.denominator == 1
    return int(h)


def m14():   # divisors of 30^6 that are perfect cubes but not perfect squares
    c = 0
    for e in product(range(7), repeat=3):
        cube = all(x % 3 == 0 for x in e)
        square = all(x % 2 == 0 for x in e)
        if cube and not square:
            c += 1
    return c


def m15():   # largest 6-digit palindrome divisible by 7 and 13 with digit sum 30
    for n in range(999999, 99999, -1):
        s = str(n)
        if s == s[::-1] and n % 91 == 0 and sum(map(int, s)) == 30:
            return n
    return -1


def m16():   # monotone paths (0,0)->(9,9) never going above y = x + 1
    N = 9
    w = [[0] * (N + 1) for _ in range(N + 1)]
    w[0][0] = 1
    for x in range(N + 1):
        for y in range(N + 1):
            if (x, y) == (0, 0) or y > x + 1:
                continue
            w[x][y] = (w[x - 1][y] if x else 0) + (w[x][y - 1] if y else 0)
    return w[N][N]


def m17():   # x in [0, 1105) with x^3 == x (mod 1105)
    return sum(1 for x in range(1105) if (x ** 3 - x) % 1105 == 0)


def m18():   # x^3 - 2083x + m with three integer roots a, b, c: |a| + |b| + |c|
    sols = set()
    for a in range(-60, 61):
        for b in range(-60, 61):
            c = -a - b
            if a * b + b * c + c * a == -2083:
                sols.add(tuple(sorted(abs(x) for x in (a, b, c))))   # (a,b,c) and (-a,-b,-c) both work
    assert len(sols) == 1, sols
    return sum(next(iter(sols)))


def m19():   # 4 red + 6 blue drawn until both colours seen: E[draws] = m/n, m + n
    from math import comb
    R, B = 4, 6
    e = Fraction(0)
    # P(first k draws all one colour, then the other colour) summed: E = sum_{k>=1} P(T > k) + 1 ... computed exactly
    total = 0
    for order in set(combinations(range(R + B), R)):
        reds = set(order)
        seq = ["R" if i in reds else "B" for i in range(R + B)]
        t = next(i for i in range(1, R + B) if seq[i] != seq[0]) + 1
        e += t
        total += 1
    e /= total
    assert total == comb(R + B, R)
    return e.numerator + e.denominator


def m20():   # ordered triples a <= b <= c of positive integers with a*b*c = 12^5
    N = 12 ** 5
    divs = [d for d in range(1, isqrt(N) + 1) if N % d == 0]
    divs = sorted(set(divs + [N // d for d in divs]))
    c = 0
    for a in divs:
        if a ** 3 > N:
            break
        rest = N // a
        for b in divs:
            if b < a:
                continue
            if b * b > rest:
                break
            if rest % b == 0 and rest // b >= b:
                c += 1
    return c


ALL = {f"m{i:02d}": globals()[f"m{i:02d}"] for i in range(1, 21)}

if __name__ == "__main__":
    for k, f in ALL.items():
        print(k, f())
