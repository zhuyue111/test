#!/usr/bin/env python3
"""Move remaining non-category directories into General/通用."""

from pathlib import Path
import shutil

CAT_NAMES = {
    "通用", "4G版", "5G版", "1G版", "Road", "Rail",
    "General", "4G Version", "5G Version", "1G Version",
}


def migrate():
    for lang in ["zh", "en"]:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for product_dir in lang_dir.iterdir():
            if not product_dir.is_dir():
                continue
            target_cat = "通用" if lang == "zh" else "General"
            for item in product_dir.iterdir():
                if not item.is_dir():
                    continue
                if item.name in CAT_NAMES:
                    continue
                dest = product_dir / target_cat / item.name
                if dest.exists():
                    for f in item.iterdir():
                        if f.is_file():
                            shutil.move(str(f), str(dest / f.name))
                            print(f"Moved: {f} -> {dest / f.name}")
                    if not any(item.iterdir()):
                        item.rmdir()
                        print(f"Removed empty: {item}")
                else:
                    shutil.move(str(item), str(dest))
                    print(f"Moved dir: {item} -> {dest}")
    print("Done.")


if __name__ == "__main__":
    migrate()
