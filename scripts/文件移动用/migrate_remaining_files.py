#!/usr/bin/env python3
from pathlib import Path
import shutil

for lang in ["zh", "en"]:
    lang_dir = Path(lang)
    if not lang_dir.exists():
        continue
    for product_dir in lang_dir.iterdir():
        if not product_dir.is_dir():
            continue
        target_cat = "通用" if lang == "zh" else "General"
        for f in product_dir.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                dest = product_dir / target_cat / f.name
                shutil.move(str(f), str(dest))
                print(f"Moved: {f} -> {dest}")
print("Done.")