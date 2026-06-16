#!/usr/bin/env python3
"""Migrate spec files into category subdirectories."""

from pathlib import Path
import shutil

CAT_ZH = ["通用", "4G版", "5G版", "1G版", "Road", "Rail"]
CAT_EN = ["General", "4G Version", "5G Version", "1G Version", "Road", "Rail"]
VALID_EXT = {".md", ".pdf"}


def migrate():
    for lang, cats in [("zh", CAT_ZH), ("en", CAT_EN)]:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            print(f"[SKIP] {lang}/ not found")
            continue
        for product_dir in lang_dir.iterdir():
            if not product_dir.is_dir():
                continue
            if product_dir.name == ".gitkeep":
                continue
            # Create category dirs
            for cat in cats:
                (product_dir / cat).mkdir(exist_ok=True)
                print(f"Created: {product_dir / cat}")
            # Move files into first category (通用/General)
            target_cat = cats[0]
            for f in product_dir.iterdir():
                if f.is_file() and f.suffix.lower() in VALID_EXT:
                    dest = product_dir / target_cat / f.name
                    shutil.move(str(f), str(dest))
                    print(f"Moved: {f} -> {dest}")
    print("Done.")


if __name__ == "__main__":
    migrate()
