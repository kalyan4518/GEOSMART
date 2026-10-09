# Architecture notes

The root `app.py` remains the stable command-line entry point and imports the Flask app from `geosmart.app`. The application package contains the existing route handlers and the configuration, persistence models, inference code, routing, and complaint/hotspot services.

Flask renders pages from the root `templates/` directory and serves assets from `static/`. `geosmart.config` anchors the database, upload, model, and static paths to the repository root. SQLite is the local default; the PostgreSQL path enables PostGIS-backed hotspot calculations.

Training run history is under `ml/runs/`; new Ultralytics runs are written there. Runtime model weights stay under root `models/` or at an environment-configured path. The TrashNet source, its original archive, and prepared classification datasets remain together under `trashnet-master/data/` because the preserved legacy code and preparation workflow depend on that structure.

The current login and profile implementations are demo-oriented and in-memory. Before a public production deployment, replace demo authentication with a real identity/account system and move volatile application state to durable shared storage.
