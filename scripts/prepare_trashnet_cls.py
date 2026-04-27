from pathlib import Path
import random
import shutil

SOURCE_ROOT = Path("trashnet-master/data/dataset-resized")
TARGET_ROOT = Path("trashnet-master/data/trashnet_cls")
SPLITS = (("train", 0.7), ("val", 0.15), ("test", 0.15))
SEED = 42


def main():
    if not SOURCE_ROOT.exists():
        raise SystemExit(f"Source dataset folder not found: {SOURCE_ROOT}")

    random.seed(SEED)
    class_dirs = sorted([p for p in SOURCE_ROOT.iterdir() if p.is_dir()])
    if not class_dirs:
        raise SystemExit("No class folders found in dataset source")

    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)

    class_names = [p.name for p in class_dirs]

    for split_name, _ in SPLITS:
        for class_name in class_names:
            (TARGET_ROOT / split_name / class_name).mkdir(parents=True, exist_ok=True)

    for class_dir in class_dirs:
        images = [p for p in class_dir.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        random.shuffle(images)
        total = len(images)

        n_train = int(total * SPLITS[0][1])
        n_val = int(total * SPLITS[1][1])
        n_test = total - n_train - n_val

        buckets = {
            "train": images[:n_train],
            "val": images[n_train:n_train + n_val],
            "test": images[n_train + n_val:n_train + n_val + n_test],
        }

        for split_name, split_images in buckets.items():
            for image_path in split_images:
                target_path = TARGET_ROOT / split_name / class_dir.name / image_path.name
                shutil.copy2(image_path, target_path)

    names_block = "\n".join([f"  {idx}: {name}" for idx, name in enumerate(class_names)])
    yaml_content = (
        f"path: {TARGET_ROOT.resolve().as_posix()}\n"
        f"train: train\n"
        f"val: val\n"
        f"test: test\n"
        f"names:\n{names_block}\n"
    )
    (TARGET_ROOT / "data.yaml").write_text(yaml_content, encoding="utf-8")

    print("Prepared dataset:", TARGET_ROOT)
    print("YAML:", TARGET_ROOT / "data.yaml")
    print("Classes:", ", ".join(class_names))


if __name__ == "__main__":
    main()
