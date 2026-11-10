"""Brute-force the S3 'puzzle' prompt (6 researchers / days / topics / beverages) to auto-check answers."""
from itertools import permutations
P = ["Ada", "Ben", "Chloe", "Dev", "Elif", "Farid"]
T = ["graphs", "compilers", "databases", "security", "robotics", "vision"]
B = ["tea", "coffee", "water", "juice", "cocoa", "soda"]
sols = []
for d in permutations(range(6)):            # day index of each person (0=Mon .. 5=Sat)
    D = dict(zip(P, d))
    if not (D["Elif"] < D["Ben"] < D["Farid"]): continue           # 2
    if D["Chloe"] in (0, 5): continue                              # 4 (day part)
    if D["Dev"] != 1: continue                                     # 6
    if D["Ada"] != D["Chloe"] + 1: continue                        # 8
    byday = {v: k for k, v in D.items()}
    for t in permutations(T):
        TT = dict(zip(P, t))
        tday = {TT[p]: D[p] for p in P}
        if tday["compilers"] not in (2, 3): continue               # 3 (day part)
        if tday["security"] != tday["databases"] + 2: continue     # 5
        if TT["Dev"] == "vision": continue                         # 6
        if tday["vision"] == 4: continue                           # 11
        for b in permutations(B):
            BB = dict(zip(P, b))
            bday = {BB[p]: D[p] for p in P}
            if tday["graphs"] + 1 != bday["cocoa"]: continue       # 1
            if BB[byday[tday["compilers"]]] == "coffee": continue  # 3
            if BB["Chloe"] != "juice": continue                    # 4
            if TT[byday[bday["water"]]] != "robotics": continue    # 7
            if bday["soda"] != 5: continue                         # 9
            if not (bday["tea"] < bday["coffee"] < 2): continue    # 10
            if BB["Elif"] == "tea": continue                       # 12
            sols.append({p: (["Mon","Tue","Wed","Thu","Fri","Sat"][D[p]], TT[p], BB[p]) for p in P})
print(len(sols), "solution(s)")
for s in sols: print(s)
