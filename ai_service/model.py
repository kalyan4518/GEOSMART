from functools import lru_cache
import importlib
import os
import shutil
from pathlib import Path

from config import BASE_DIR, Config, MODEL_PATH

try:
    import cv2
except Exception:
    cv2 = None

try:
    import numpy as np
except Exception:
    np = None

try:
    tf = importlib.import_module("tensorflow")
except Exception:
    tf = None

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


CNN_CLASS_NAMES = ["cardboard", "glass", "metal", "paper", "plastic", "trash"]

WASTE_LABEL_HINTS = {
    "cardboard",
    "paper",
    "plastic",
    "glass",
    "metal",
    "trash",
    "organic",
    "recyclable",
    "biomedical",
    "hazardous",
    "ewaste",
}

# Per-class thresholds to reduce wrong final labels on visually similar classes.
DEFAULT_CONF_THRESHOLD = 0.65
DEFAULT_MARGIN_THRESHOLD = 0.15
CLASS_CONF_THRESHOLDS = {
    "cardboard": 0.68,
    "glass": 0.72,
    "metal": 0.74,
    "paper": 0.66,
    "plastic": 0.70,
    "trash": 0.70,
    "organic": 0.65,
    "recyclable": 0.65,
}
CLASS_MARGIN_THRESHOLDS = {
    "glass": 0.18,
    "metal": 0.20,
    "plastic": 0.17,
}


def _empty_result(predicted_type="unavailable"):
    return {
        "verified": False,
        "verification_score": 0.0,
        "predicted_type": predicted_type,
        "model": "unavailable",
    }


def _is_waste_like_label(label):
    normalized = (label or "").strip().lower().replace("-", " ")
    if not normalized:
        return False
    tokens = set(normalized.split())
    if tokens & WASTE_LABEL_HINTS:
        return True
    return any(hint in normalized for hint in WASTE_LABEL_HINTS)


def _incompatible_model_result(predicted_type, model_name):
    return {
        "verified": False,
        "verification_score": 0.0,
        "predicted_type": predicted_type or "unknown",
        "model": f"{model_name} (incompatible labels)",
    }


def _threshold_key(label):
    normalized = (label or "").strip().lower().replace("-", " ")
    if not normalized:
        return None

    for key in CLASS_CONF_THRESHOLDS:
        if normalized == key or key in normalized:
            return key
    return normalized


def _is_prediction_verified(predicted_type, confidence, margin=None):
    key = _threshold_key(predicted_type)
    class_conf = CLASS_CONF_THRESHOLDS.get(key, max(Config.VERIFIED_THRESHOLD, DEFAULT_CONF_THRESHOLD))
    class_margin = CLASS_MARGIN_THRESHOLDS.get(key, DEFAULT_MARGIN_THRESHOLD)

    if confidence < class_conf:
        return False
    if margin is not None and margin < class_margin:
        return False
    return True


def _candidate_cnn_model_paths():
    env_path = os.environ.get("GEOSMART_CNN_MODEL_PATH", "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            BASE_DIR / "mymodel.h5",
            BASE_DIR / "models" / "mymodel.h5",
            BASE_DIR / "models" / "waste_cnn.h5",
        ]
    )

    deduped = []
    seen = set()
    for path in candidates:
        resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


@lru_cache(maxsize=1)
def _load_cnn_model():
    if tf is None:
        return None

    for model_path in _candidate_cnn_model_paths():
        if not model_path.exists():
            continue
        try:
            return tf.keras.models.load_model(str(model_path))
        except Exception:
            continue

    return None


def _predict_with_cnn(image_file):
    if cv2 is None or np is None:
        return None

    model = _load_cnn_model()
    if model is None:
        return None

    img = cv2.imread(str(image_file))
    if img is None:
        return None

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (224, 224))
    img = img.astype("float32") / 255.0

    try:
        prediction = model.predict(np.expand_dims(img, axis=0), verbose=0)
        if prediction is None or len(prediction) == 0:
            return None

        probs = prediction[0]
        class_id = int(np.argmax(probs))
        confidence = float(probs[class_id])
        predicted_type = CNN_CLASS_NAMES[class_id] if 0 <= class_id < len(CNN_CLASS_NAMES) else str(class_id)
        return {
            "verified": _is_prediction_verified(predicted_type, confidence),
            "verification_score": round(confidence, 4),
            "predicted_type": predicted_type,
            "model": "Notebook CNN (.h5)",
        }
    except Exception:
        return None


def _candidate_model_paths():
    env_path = os.environ.get("GEOSMART_MODEL_PATH", "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    # Prefer project-trained waste models first. Keep generic models as fallback.
    candidates.extend(
        [
            MODEL_PATH,
            BASE_DIR / "models" / "waste_model.pt",
        ]
    )

    trained_best = list((BASE_DIR / "runs").glob("geosmart-cls*/*/best.pt"))
    trained_best.extend(list((BASE_DIR / "runs").glob("geosmart-cls*/weights/best.pt")))
    trained_best = [p for p in trained_best if p.exists()]
    trained_best.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    candidates.extend(trained_best)

    # Do not prioritize generic imagenet-like classifiers for waste decisions.
    # Keep this file only as an optional last resort in case user explicitly wants it.
    candidates.append(BASE_DIR / "yolo11n-cls.pt")

    deduped = []
    seen = set()
    for path in candidates:
        resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


@lru_cache(maxsize=1)
def _load_model():
    if YOLO is None:
        return None, None

    for model_path in _candidate_model_paths():
        if not model_path.exists():
            continue
        try:
            return YOLO(str(model_path)), str(model_path)
        except Exception:
            continue

    return None, None


def _class_name(names, class_id):
    if isinstance(names, dict):
        return names.get(class_id, str(class_id))
    if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
        return names[class_id]
    return str(class_id)


def verify_waste(image_path):
    image_file = Path(image_path)
    if not image_file.exists():
        return _empty_result()

    cnn_result = _predict_with_cnn(image_file)
    if cnn_result is not None:
        return cnn_result

    model, model_source = _load_model()
    if model is None:
        return _empty_result()

    try:
        results = model.predict(source=str(image_file), verbose=False, conf=0.01, imgsz=224, device="cpu")
        if not results:
            return _empty_result()

        result = results[0]
        probs = getattr(result, "probs", None)
        if probs is not None and getattr(probs, "top1", None) is not None:
            class_id = int(probs.top1)
            top1_conf = getattr(probs, "top1conf", None)
            confidence = float(top1_conf.item()) if top1_conf is not None else 0.0
            predicted_type = _class_name(result.names, class_id)

            if not _is_waste_like_label(predicted_type):
                return _incompatible_model_result(
                    predicted_type,
                    f"YOLO classifier ({Path(model_source).name})" if model_source else "YOLO classifier",
                )

            confidence_margin = 0.0
            prob_data = getattr(probs, "data", None)
            if prob_data is not None:
                try:
                    values = prob_data.detach().cpu().numpy().tolist()
                    if isinstance(values, list) and values:
                        ordered = sorted([float(v) for v in values], reverse=True)
                        if len(ordered) > 1:
                            confidence_margin = ordered[0] - ordered[1]
                except Exception:
                    confidence_margin = 0.0

            return {
                "verified": _is_prediction_verified(predicted_type, confidence, confidence_margin),
                "verification_score": round(confidence, 4),
                "predicted_type": predicted_type,
                "model": f"YOLO classifier ({Path(model_source).name})" if model_source else "YOLO classifier",
            }

        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return _empty_result()

        conf_values = getattr(boxes, "conf", None)
        cls_values = getattr(boxes, "cls", None)
        if conf_values is None or cls_values is None or len(conf_values) == 0:
            return _empty_result()

        top_index = int(conf_values.argmax().item())
        confidence = float(conf_values[top_index].item())
        class_id = int(cls_values[top_index].item())
        predicted_type = _class_name(result.names, class_id)

        if not _is_waste_like_label(predicted_type):
            return _incompatible_model_result(
                predicted_type,
                f"YOLO detector ({Path(model_source).name})" if model_source else "YOLO detector",
            )

        return {
            "verified": _is_prediction_verified(predicted_type, confidence),
            "verification_score": round(confidence, 4),
            "predicted_type": predicted_type,
            "model": f"YOLO detector ({Path(model_source).name})" if model_source else "YOLO detector",
        }
    except Exception:
        return _empty_result()


def train_waste_model(data_path, epochs=25, imgsz=224, base_model="yolo11n-cls.pt", batch=64):
    if YOLO is None:
        raise RuntimeError("Ultralytics is not installed in this environment.")

    dataset = Path(data_path)
    if not dataset.exists():
        raise RuntimeError(f"Dataset path not found: {dataset}")

    # Ultralytics classification trainer expects a directory with train/val/test folders.
    # If a YAML file is provided, use its parent directory.
    if dataset.is_file() and dataset.suffix.lower() in {".yaml", ".yml"}:
        dataset = dataset.parent

    model = YOLO(base_model)
    run_name = f"geosmart-cls-{Path(data_path).stem}"
    train_results = model.train(
        data=str(dataset),
        epochs=int(epochs),
        imgsz=int(imgsz),
        batch=int(batch),
        workers=0,
        plots=False,
        project=str(BASE_DIR / "runs"),
        name=run_name,
        verbose=False,
    )

    trainer = getattr(model, "trainer", None)
    best_path = None
    if trainer is not None:
        maybe_best = getattr(trainer, "best", None)
        if maybe_best:
            best_path = Path(str(maybe_best))

    if best_path is None:
        save_dir = Path(getattr(train_results, "save_dir", BASE_DIR / "runs" / run_name))
        fallback = save_dir / "weights" / "best.pt"
        best_path = fallback if fallback.exists() else None

    if best_path and best_path.exists():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_path, MODEL_PATH)
        _load_model.cache_clear()
        _load_cnn_model.cache_clear()

    return {
        "run_name": run_name,
        "best_model_path": str(best_path) if best_path else None,
    }