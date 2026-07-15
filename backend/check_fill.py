import requests

# adjust these ids to real ones in your DB if any are missing
mat_ids = ["clinker", "wheat", "sand_dry", "fly_ash", "coal"]

for mid in mat_ids:
    r = requests.get(f"http://127.0.0.1:8000/api/v1/materials/{mid}")
    if r.status_code != 200:
        print(f"{mid:12s} -- not found ({r.status_code})")
        continue
    m = r.json()
    print(f"{mid:12s} "
          f"flow={m.get('flowability')} "
          f"class={m.get('particle_class')} "
          f"cema={m.get('cema_code')} "
          f"FILL={m.get('bucket_fill_factor')} "
          f"fill_max={m.get('fill_max')}")