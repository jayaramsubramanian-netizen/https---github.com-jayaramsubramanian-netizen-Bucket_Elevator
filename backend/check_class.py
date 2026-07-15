import requests
mats = requests.get("http://127.0.0.1:8000/api/v1/materials").json()
mats = mats.get("materials", mats) if isinstance(mats, dict) else mats

from collections import Counter
flow = Counter(m.get("flowability") for m in mats)
pcls = Counter(m.get("particle_class") for m in mats)
haz  = Counter(bool(m.get("hazard_codes")) for m in mats)
print(f"total materials: {len(mats)}")
print("flowability populated:", dict(flow))
print("particle_class populated:", dict(pcls))
print("has hazard_codes:", dict(haz))