"""Shared authentication, upload, training, and presentation helpers."""

import threading
import zipfile
from functools import wraps
from pathlib import Path

import yaml
from flask import jsonify, redirect, request, session, url_for

from geosmart.ai_service.model import train_waste_model
from geosmart.config import BASE_DIR, Config, ISSUE_TYPES

profiles_store = {}
training_state = {
    "status": "idle",
    "message": "No training run started yet.",
    "runName": None,
    "bestModelPath": None,
}
dataset_upload_dir = BASE_DIR / "uploads" / "datasets"
dataset_upload_dir.mkdir(parents=True, exist_ok=True)

def _is_authenticated():
    return bool(session.get("user"))


def _is_admin():
    return session.get("role") == "admin"


def require_auth(admin_only=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            is_api = request.path.startswith("/api/")
            if not _is_authenticated():
                if is_api:
                    return jsonify({"error": "Authentication required."}), 401
                return redirect(url_for("login"))
            if admin_only and not _is_admin():
                if is_api:
                    return jsonify({"error": "Admin access required."}), 403
                return redirect(url_for("dashboard"))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def inject_session_context():
    return {
        "current_user": session.get("user", "Guest"),
        "current_role": session.get("role", "guest"),
        "is_admin": _is_admin(),
        "is_authenticated": _is_authenticated(),
    }


def _start_training_async(data_path, epochs, imgsz):
    training_state["status"] = "running"
    training_state["message"] = "Training in progress..."
    training_state["runName"] = None
    training_state["bestModelPath"] = None

    def runner():
        try:
            result = train_waste_model(data_path=data_path, epochs=epochs, imgsz=imgsz)
            training_state["status"] = "completed"
            training_state["message"] = "Training completed successfully."
            training_state["runName"] = result.get("run_name")
            training_state["bestModelPath"] = result.get("best_model_path")
        except Exception as exc:
            training_state["status"] = "failed"
            training_state["message"] = str(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


def _parse_yaml_file(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise RuntimeError("Dataset YAML is invalid. It must be a mapping/object.")
    return payload


def _resolve_data_path(dataset_path):
    raw = Path(dataset_path)
    candidate = raw if raw.is_absolute() else (BASE_DIR / raw)
    return candidate.resolve()


def _validate_dataset_path(dataset_path):
    resolved = _resolve_data_path(dataset_path)
    if not resolved.exists():
        raise RuntimeError(f"Dataset path not found: {resolved}")

    if resolved.is_file() and resolved.suffix.lower() in {".yaml", ".yml"}:
        payload = _parse_yaml_file(resolved)
        required_keys = ["train", "val", "names"]
        missing = [key for key in required_keys if key not in payload]
        if missing:
            raise RuntimeError("Dataset YAML missing required keys: " + ", ".join(missing))

        dataset_root_value = payload.get("path", ".")
        if not isinstance(dataset_root_value, str):
            raise RuntimeError("Dataset YAML 'path' must be a string.")
        dataset_root = Path(dataset_root_value).expanduser()
        if not dataset_root.is_absolute():
            dataset_root = (resolved.parent / dataset_root).resolve()

        for split_name in ("train", "val"):
            split_value = payload[split_name]
            split_paths = split_value if isinstance(split_value, list) else [split_value]
            if not split_paths or any(not isinstance(value, str) for value in split_paths):
                raise RuntimeError(f"Dataset YAML '{split_name}' must be a path or list of paths.")
            for split_path in split_paths:
                location = Path(split_path).expanduser()
                if not location.is_absolute():
                    location = dataset_root / location
                if not location.is_dir():
                    raise RuntimeError(f"Dataset {split_name} path not found: {location}")

        names = payload.get("names")
        class_count = len(names) if isinstance(names, list) else len(names.keys()) if isinstance(names, dict) else 0
        if class_count == 0:
            raise RuntimeError("Dataset YAML 'names' must contain at least one class.")
        return {
            "resolvedPath": str(resolved),
            "classCount": class_count,
            "classes": names,
            "train": payload.get("train"),
            "val": payload.get("val"),
        }

    if not resolved.is_dir():
        raise RuntimeError("Dataset path must be a directory or YAML file.")

    train_dir = resolved / "train"
    val_dir = resolved / "val"
    if not train_dir.exists() or not val_dir.exists():
        raise RuntimeError("Classification directory must contain train/ and val/ folders.")

    class_names = sorted([p.name for p in train_dir.iterdir() if p.is_dir()])
    if not class_names:
        raise RuntimeError("No class folders found under train/.")

    return {
        "resolvedPath": str(resolved),
        "classCount": len(class_names),
        "classes": class_names,
        "train": "train",
        "val": "val",
    }


def _safe_extract_zip(zip_path, target_dir):
    destination_root = Path(target_dir).resolve()
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        for member in members:
            member_path = (destination_root / member.filename).resolve()
            try:
                member_path.relative_to(destination_root)
            except ValueError as exc:
                raise RuntimeError("Unsafe zip content detected.") from exc
        archive.extractall(target_dir)


def _build_cnn_item_insight(predicted_type):
    label = (predicted_type or "Unknown item").strip()
    normalized = label.lower()

    catalog = [
        {
            "keywords": ["plastic"],
            "itemInfo": "Plastic item detected. Clean and dry plastics are commonly recyclable.",
            "recyclable": True,
            "recycleLabel": "Useful for recycling",
            "guidance": "Rinse, dry, and send to dry-waste collection. Avoid mixing with food waste.",
        },
        {
            "keywords": ["glass"],
            "itemInfo": "Glass item detected. Most glass containers are recyclable.",
            "recyclable": True,
            "recycleLabel": "Useful for recycling",
            "guidance": "Keep separate from mixed waste and avoid breakage during collection.",
        },
        {
            "keywords": ["metal", "aluminium", "aluminum", "can"],
            "itemInfo": "Metal item detected. Metals generally have high recovery value.",
            "recyclable": True,
            "recycleLabel": "Useful for recycling",
            "guidance": "Send to dry-waste or scrap stream after removing food residue.",
        },
        {
            "keywords": ["paper", "cardboard", "carton"],
            "itemInfo": "Paper/cardboard detected. Usually recyclable when dry and clean.",
            "recyclable": True,
            "recycleLabel": "Useful for recycling",
            "guidance": "Keep dry. Oily or wet paper should go to organic/residual handling.",
        },
        {
            "keywords": ["organic", "food", "biodegradable"],
            "itemInfo": "Organic waste detected. Better for composting than recycling.",
            "recyclable": False,
            "recycleLabel": "Not for dry recycling",
            "guidance": "Send to wet-waste stream for composting or bio-methanation.",
        },
        {
            "keywords": ["trash", "mixed"],
            "itemInfo": "Mixed/residual waste detected. Usually low recycling value.",
            "recyclable": False,
            "recycleLabel": "Not suitable for direct recycling",
            "guidance": "Try source segregation first. Only clean recoverables should go to recycling.",
        },
        {
            "keywords": ["hazard", "biomedical", "battery", "e-waste", "ewaste"],
            "itemInfo": "Hazardous stream detected. Requires specialized handling.",
            "recyclable": False,
            "recycleLabel": "Special handling required",
            "guidance": "Do not mix with household dry waste. Use authorized hazardous/e-waste collection.",
        },
    ]

    for entry in catalog:
        if any(keyword in normalized for keyword in entry["keywords"]):
            return {
                "itemName": label,
                "itemInfo": entry["itemInfo"],
                "recyclable": entry["recyclable"],
                "recycleLabel": entry["recycleLabel"],
                "guidance": entry["guidance"],
            }

    return {
        "itemName": label,
        "itemInfo": "Item detected, but recycling category is uncertain.",
        "recyclable": False,
        "recycleLabel": "Needs manual check",
        "guidance": "Please verify item type manually before sending it to recycling.",
    }


def _load_dashboard_carousel_images(limit=12):
    uploads_dir = BASE_DIR / "static" / "uploads"
    if not uploads_dir.exists():
        return []

    allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    files = [p for p in uploads_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    selected = files[:limit]

    return [url_for("static", filename=f"uploads/{p.name}") for p in selected]

