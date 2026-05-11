import json, requests

samples = ["01_acme_SOV.xlsx", "02_cascade_SOV.xlsx",
           "03_magnolia_SOV.xlsx", "06_coastal_SOV.xlsx"]

for s in samples:
    print(f"\n=== {s} ===", flush=True)
    r = requests.post("http://localhost:8000/sov/extract/pipeline",
                      json={"sample_name": s, "pipeline_id": "xlsx_via_pdf_tiff",
                            "save_as_canonical": True},
                      timeout=600)
    if r.status_code != 200:
        print(f"  EXTRACT FAIL {r.status_code}: {r.text[:300]}"); continue
    ex = r.json()
    print(f"  locs={ex['location_count_actual']}  run={ex['meta'].get('run_id')}")

    v = requests.post("http://localhost:8000/sov/validate",
                     json={"sample_name": s}, timeout=120)
    if v.status_code != 200:
        print(f"  VALIDATE FAIL {v.status_code}: {v.text[:300]}"); continue
    val = v.json()
    summ = val["summary"]
    print(f"  acct_mis_in_src={summ['account_mismatches_in_source']}  "
          f"loc_mis_in_src={summ['location_mismatches_in_source']}  "
          f"locs={summ['location_count_actual']}/{summ['location_count_expected']}")

    real = [d for d in val["account"] if d.get("in_source") and not d["match"]]
    if real:
        print("  ACCOUNT mismatches (in source):")
        for d in real:
            print(f"    - {d['field']}: got={d['actual']!r} exp={d['expected']!r}")

    real_loc = [d for d in val["locations"] if d.get("in_source") and not d["match"]]
    if real_loc:
        print(f"  LOCATION mismatches (in source) [{len(real_loc)}]:")
        for d in real_loc[:30]:
            print(f"    - loc {d['location_key']}.{d['field']}: "
                  f"got={d['actual']!r} exp={d['expected']!r}")
        if len(real_loc) > 30:
            print(f"    ... +{len(real_loc)-30} more")

    if not real and not real_loc:
        print("  CLEAN")
