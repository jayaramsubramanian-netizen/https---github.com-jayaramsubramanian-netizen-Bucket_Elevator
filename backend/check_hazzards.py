import requests
from collections import Counter
mats = requests.get("http://127.0.0.1:8000/api/v1/materials").json()
mats = mats.get("materials", mats) if isinstance(mats, dict) else mats

codes = Counter()
for m in mats:
    h = m.get("hazard_codes")
    if h:
        for token in str(h).replace(";", ",").split(","):
            codes[token.strip()] += 1
print("distinct hazard codes and counts:")
for code, n in codes.most_common():
    print(f"  {code:12s} {n}")