#!/usr/bin/env python3
"""Migrate image directories into category subdirectories."""

from pathlib import Path
import shutil

CAT_ZH = "通用"
CAT_EN = "General"
IMG_DIRS = {"images", "img", "imgs"}


def migrate():
    for lang, cat_name in [("zh", CAT_ZH), ("en", CAT_EN)]:
        lang_dir = Path(lang)
        if not lang_dir.exists():
            continue
        for product_dir in lang_dir.iterdir():
            if not product_dir.is_dir():
                continue
            for img_dir_name in IMG_DIRS:
                img_dir = product_dir / img_dir_name
                if img_dir.exists() and img_dir.is_dir():
                    dest = product_dir / cat_name / img_dir_name
                    if dest.exists():
                        # Merge contents
                        for f in img_dir.iterdir():
                            if f.is_file():
                                shutil.move(str(f), str(dest / f.name))
                                print(f"Moved: {f} -> {dest / f.name}")
                        # Remove empty source dir
                        if not any(img_dir.iterdir()):
                            img_dir.rmdir()
                            print(f"Removed empty: {img_dir}")
                    else:
                        shutil.move(str(img_dir), str(dest))
                        print(f"Moved dir: {img_dir} -> {dest}")
    print("Done.")


if __name__ == "__main__":
    migrate()
