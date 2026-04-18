import json
nb = json.load(open("test_ai_api.ipynb", encoding="utf-8"))
for i, c in enumerate(nb["cells"]):
    src = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
    cid = c.get("id", "?")
    print(f"Cell {i+1} [{c['cell_type']}] id={cid}")
    print(f"  {src[:100].strip()}")
    print()
