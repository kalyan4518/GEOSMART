from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE = PROJECT_ROOT / "trashnet-master" / "data" / "trashnet_cls"
TARGET = PROJECT_ROOT / "trashnet-master" / "data" / "trashnet_cls_tiny"
LIMITS = {
    "train": 30,
    "val": 8,
    "test": 8,
}


def main():
    if TARGET.exists():
        shutil.rmtree(TARGET)

    for split, limit in LIMITS.items():
        split_src = SOURCE / split
        split_dst = TARGET / split
        classes = [p for p in split_src.iterdir() if p.is_dir()]
        for class_dir in classes:
            out_dir = split_dst / class_dir.name
            out_dir.mkdir(parents=True, exist_ok=True)
            images = [p for p in class_dir.iterdir() if p.is_file()]
            for image_path in images[:limit]:
                shutil.copy2(image_path, out_dir / image_path.name)

    print(TARGET.resolve())


if __name__ == "__main__":
    main()
