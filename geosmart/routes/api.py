"""JSON API routes for complaints, dashboards, training, and inference."""

from pathlib import Path
import tempfile
import uuid

from flask import jsonify, redirect, render_template, request, session, url_for

from geosmart.app_core import app
from geosmart.config import BASE_DIR, Config, ISSUE_TYPES, session_scope
from geosmart.web_support import (
    _build_cnn_item_insight,
    _is_admin,
    _is_authenticated,
    _safe_extract_zip,
    _start_training_async,
    _validate_dataset_path,
    dataset_upload_dir,
    profiles_store,
    require_auth,
    training_state,
)
from geosmart.ai_service.model import is_valid_image_file, verify_waste
from geosmart.services.complaint_service import (
    create_complaint,
    list_complaints,
    update_complaint_status,
)
from geosmart.services.hotspot_service import (
    build_dashboard_summary,
    build_heatmap,
    get_route_payload,
    list_hotspots,
)
@app.route("/api/complaints", methods=["GET"])
@require_auth()
def api_get_complaints():
    current_user = session.get("user", "")
    with session_scope() as db_session:
        if _is_admin():
            return jsonify(list_complaints(db_session))
        return jsonify(list_complaints(db_session, contact=current_user))


@app.route("/api/complaints", methods=["POST"])
@require_auth()
def api_create_complaint():
    if request.files:
        payload = request.form.to_dict(flat=True)
        image_file = request.files.get("image")
    else:
        payload = request.get_json(silent=True) or {}
        image_file = None

    current_user = session.get("user", "")
    # Always map citizen-submitted complaints to the logged-in user so
    # the user dashboard can reliably show "my complaints" history.
    if current_user and not _is_admin():
        payload["contact"] = current_user
    elif current_user and not payload.get("contact"):
        payload["contact"] = current_user

    with session_scope() as db_session:
        record = create_complaint(db_session, payload, image_file=image_file)
        return jsonify(record), 201


@app.route("/api/complaints/<complaint_id>/status", methods=["PATCH"])
@require_auth(admin_only=True)
def api_update_complaint_status(complaint_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ("Pending", "Assigned", "In Progress", "Resolved"):
        return jsonify({"error": "Invalid status"}), 400

    with session_scope() as db_session:
        complaint = update_complaint_status(db_session, complaint_id, new_status)
        if not complaint:
            return jsonify({"error": "Not found"}), 404
        return jsonify(complaint)


@app.route("/api/hotspots", methods=["GET"])
@require_auth()
def api_hotspots():
    with session_scope() as db_session:
        hotspots = list_hotspots(db_session, refresh=True)
        heatmap = build_heatmap(db_session)
        summary = build_dashboard_summary(db_session)
        return jsonify({
            "generatedAt": summary["generatedAt"],
            "hotspots": hotspots,
            "heatmap": heatmap,
        })


@app.route("/api/routes/optimize", methods=["GET"])
@require_auth()
def api_optimize_route():
    hotspot_id = request.args.get("hotspotId")
    with session_scope() as db_session:
        route_payload = get_route_payload(db_session, hotspot_id)
        if not route_payload:
            return jsonify({"error": "No hotspot available"}), 404
        return jsonify(route_payload)


@app.route("/api/dashboard-summary", methods=["GET"])
@require_auth()
def api_dashboard_summary():
    with session_scope() as db_session:
        return jsonify(build_dashboard_summary(db_session))


@app.route("/api/profile", methods=["GET"])
@require_auth()
def api_get_profile():
    profile_data = profiles_store.get(
        "default",
        {
            "name": "Ananya Rao",
            "email": "ananya@geosmart.org",
            "location": "Ward 14, Koramangala",
            "role": "Community Sustainability Officer",
            "organisation": "GEOSMART Foundation",
        },
    )
    return jsonify(profile_data)


@app.route("/api/profile", methods=["PUT"])
@require_auth()
def api_update_profile():
    data = request.get_json(silent=True) or {}
    profiles_store["default"] = {
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "location": data.get("location", ""),
        "role": data.get("role", "Community Sustainability Officer"),
        "organisation": data.get("organisation", ""),
    }
    return jsonify(profiles_store["default"])


@app.route("/api/model/train", methods=["POST"])
@require_auth(admin_only=True)
def api_train_model():
    if training_state["status"] == "running":
        return jsonify({"error": "Training is already running."}), 409

    payload = request.get_json(silent=True) or {}
    data_path = payload.get("dataPath", "").strip()
    epochs = int(payload.get("epochs", 25))
    imgsz = int(payload.get("imgsz", 224))

    if not data_path:
        return jsonify({"error": "dataPath is required."}), 400

    _start_training_async(data_path=data_path, epochs=epochs, imgsz=imgsz)
    return jsonify({"status": "started", "message": "Training started."}), 202


@app.route("/api/model/validate-dataset", methods=["POST"])
@require_auth(admin_only=True)
def api_validate_dataset():
    payload = request.get_json(silent=True) or {}
    data_path = payload.get("dataPath", "").strip()
    if not data_path:
        return jsonify({"error": "dataPath is required."}), 400

    try:
        summary = _validate_dataset_path(data_path)
        return jsonify({"status": "valid", "summary": summary})
    except Exception as exc:
        return jsonify({"status": "invalid", "error": str(exc)}), 400


@app.route("/api/model/upload-dataset-zip", methods=["POST"])
@require_auth(admin_only=True)
def api_upload_dataset_zip():
    if training_state["status"] == "running":
        return jsonify({"error": "Cannot upload a dataset while training is running."}), 409

    zip_file = request.files.get("datasetZip")
    if not zip_file or not zip_file.filename:
        return jsonify({"error": "datasetZip file is required."}), 400
    if not zip_file.filename.lower().endswith(".zip"):
        return jsonify({"error": "Please upload a .zip dataset archive."}), 400

    run_id = uuid.uuid4().hex[:10]
    target_dir = dataset_upload_dir / f"dataset-{run_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_path = target_dir / "dataset.zip"
    zip_file.save(zip_path)

    try:
        _safe_extract_zip(zip_path, target_dir)
        discovered = list(target_dir.rglob("data.yaml"))
        if not discovered:
            raise RuntimeError("No data.yaml found inside uploaded zip.")
        data_yaml = discovered[0]
        summary = _validate_dataset_path(str(data_yaml))
        return jsonify(
            {
                "status": "uploaded",
                "dataYamlPath": summary["resolvedPath"],
                "summary": summary,
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/model/train-status", methods=["GET"])
@require_auth(admin_only=True)
def api_train_status():
    return jsonify(training_state)


@app.route("/api/analyze/cnn", methods=["POST"])
@require_auth()
def api_analyze_cnn():
    image_file = request.files.get("image")
    if not image_file or not image_file.filename:
        return jsonify({"error": "image file is required."}), 400

    suffix = Path(image_file.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        return jsonify({"error": "Please upload a PNG, JPG, JPEG, or WEBP image."}), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            image_file.save(tmp.name)
            temp_path = tmp.name

        try:
            image_is_valid = is_valid_image_file(temp_path)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        if not image_is_valid:
            return jsonify({"error": "The uploaded file is not a readable image."}), 400

        prediction = verify_waste(temp_path)
        model_name = prediction.get("model", "unavailable")
        if (
            model_name == "unavailable"
            or prediction.get("predicted_type") == "unavailable"
        ):
            return jsonify(
                {
                    "error": (
                        "The waste classification model is unavailable or inference failed. "
                        "Check the server logs and install a compatible trained model."
                    ),
                    "status": "Model unavailable",
                }
            ), 503
        if "incompatible labels" in model_name.lower():
            return jsonify(
                {
                    "error": "The loaded model does not have waste-specific class labels.",
                    "status": "Model unavailable",
                }
            ), 503

        status = "Verified" if prediction["verified"] else "Needs review"
        confidence = float(prediction["verification_score"])
        if prediction["verified"]:
            confidence_note = "High confidence classification."
        else:
            confidence_note = "Low confidence result. Try a clearer, well-lit photo for better accuracy."
        insight = _build_cnn_item_insight(prediction["predicted_type"])
        return jsonify(
            {
                "predictedType": prediction["predicted_type"],
                "confidence": round(confidence, 4),
                "status": status,
                "model": model_name,
                "confidenceNote": confidence_note,
                "itemInfo": insight["itemInfo"],
                "recyclable": insight["recyclable"],
                "recycleLabel": insight["recycleLabel"],
                "guidance": insight["guidance"],
            }
        )
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass

