# GEOSMART

GEOSMART is a Flask waste-intelligence application for citizen waste reports, image-based waste verification, municipal hotspot monitoring, and collection route suggestions. This repository is an existing application; its Flask routes and browser-facing API contracts are retained.

## Features

- Flask and Jinja pages for sign-in, dashboards, analysis, complaints, and municipal views.
- Complaint and hotspot storage with SQLite by default and optional PostgreSQL/PostGIS support.
- Complaint evidence uploads and optional YOLO or Keras image inference.
- Dataset validation/upload and administrator-triggered Ultralytics training.
- Hotspot summaries and A* route suggestions.

## Technology

- Python 3.10–3.14 (64-bit recommended; the project was verified with Python 3.14).
- Flask, SQLAlchemy, GeoAlchemy2, PyYAML, OpenCV, and Ultralytics/PyTorch.
- Jinja templates, browser JavaScript, Leaflet, and CDN-hosted frontend libraries.

## Project layout

```text
GEOSMART/
├── app.py                       # Windows-friendly Flask entry point
├── geosmart/
│   ├── app.py                    # Flask routes and app setup
│   ├── app_core.py               # Shared Flask instance
│   ├── config.py                 # Environment, database, and domain configuration
│   ├── web_support.py            # Shared web helpers and upload/training state
│   ├── ai_service/               # Inference and model training
│   ├── models/                   # SQLAlchemy complaint and hotspot models
│   ├── routing/                  # A* route planning
│   ├── routes/                   # Page, API, and error handlers
│   └── services/                 # Complaint and hotspot operations
├── models/                       # Optional runtime model weights
├── ml/
│   ├── runs/                     # Preserved training metrics and plots
│   └── training/                 # Dataset utilities, notes, and CNN notebook
├── trashnet-master/              # Preserved source dataset and legacy TrashNet code
├── templates/                    # Flask/Jinja pages
├── static/                       # CSS, JavaScript, and user uploads
├── tests/                        # Application smoke tests
├── docs/
├── requirements.txt
├── .env.example
└── run.bat
```

`trashnet-master/data/` retains the source archive and both prepared classification datasets. No dataset or training output was removed. The legacy top-level `index.html` was removed because Flask serves the pages in `templates/` and the file had no references.

## Prerequisites

- 64-bit Python 3.10–3.14 and Windows PowerShell or Command Prompt.
- Internet access for installing dependencies and for frontend libraries loaded from CDNs.
- A waste-trained `.pt` or `.h5` model is needed for image predictions. The supplied checkout has the six-class TrashNet dataset and training workflow, but no trained checkpoint; use the training panel on `/analyze` or `geosmart.ai_service.model.train_waste_model` to create one.
- Optional: PostgreSQL with PostGIS for geospatial database operations. SQLite is the default.

## Install on Windows

From the repository directory:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

In Command Prompt, activate with `.venv\Scripts\activate.bat`. Edit `.env` and set a strong `SECRET_KEY`; set `ADMIN_PASSWORD` to enable administrator login. The included `.env.example` contains placeholders only. Keep `.env` private.

Start the server from any current directory by calling the repository's `run.bat`, or from the project root run:

```powershell
py -3.14 app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Press `Ctrl+C` in the server terminal to stop it. You can also run `python -m geosmart` from the project root.

The launcher does not install packages automatically. It checks that `.venv` exists and that the app dependencies import successfully, then starts Flask. If setup is incomplete it prints the required setup commands.

## Use the application

- `/` opens the splash page; `/index` opens the landing page.
- `/login` and `/signup` provide the existing demo user flows. The current user login is not backed by an account system and accepts any non-empty credentials; do not treat it as production authentication.
- `/admin/login` requires `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`. Admin access remains disabled when no admin password is configured.
- Submit complaints at `/complaint`; evidence and dataset uploads are stored locally. The configured maximum request size is 8 MiB.
- Use `/analyze` for image checks and administrator model-training controls.
- Model routes include `/api/analyze/cnn`, `/api/model/validate-dataset`, `/api/model/upload-dataset-zip`, `/api/model/train`, and `/api/model/train-status`.

## Models and training data

Runtime model weights belong in `models/` or at the path configured by `GEOSMART_MODEL_PATH`. CNN `.h5` weights can be configured with `GEOSMART_CNN_MODEL_PATH`; TensorFlow is optional and is not installed by the default requirements. Model weight extensions are ignored by Git, so train or provide them separately when deploying.

Training outputs are written to `ml/runs/`. The existing TrashNet data is kept in `trashnet-master/data/`. From any working directory, rebuild the classification split with:

```powershell
py -3.14 ml/training/scripts/prepare_trashnet_cls.py
```

This script replaces the prepared `trashnet_cls` output directory, so retain any local changes there before running it. A small subset can be generated with `py -3.14 ml/training/scripts/make_tiny_cls_subset.py`.

## Configuration

The application reads `.env` from the repository root when `python-dotenv` is installed. Supported values include:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Stable Flask session signing key |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Administrator login; password must be set to enable it |
| `DATABASE_URL` | SQLAlchemy URL; defaults to a project-root SQLite database |
| `GEOSMART_MODEL_PATH`, `GEOSMART_CNN_MODEL_PATH` | Optional inference weights |
| `HOTSPOT_CLUSTER_EPS_METERS`, `HOTSPOT_MIN_POINTS` | Hotspot configuration |
| `VERIFIED_THRESHOLD`, `RESPONSE_SPEED_KMPH` | Prediction and route tuning |

## Tests and checks

Run the smoke tests with:

```powershell
py -3.14 -m unittest discover -s tests -v
```

The tests exercise Flask page rendering, static file serving, authentication gates, image validation and prediction response handling, seeded complaint/hotspot APIs, and route summaries. The model's real prediction quality must be checked against a held-out dataset; returning a prediction alone does not establish accuracy.

## Troubleshooting

- **`python` not found:** use the Windows Python launcher, for example `py -3.14 app.py`.
- **Launcher says `.venv` is missing:** run the installation commands above.
- **Dependency import fails:** activate `.venv`, then run `python -m pip install -r requirements.txt`.
- **Admin login fails:** set `ADMIN_EMAIL` and a non-empty `ADMIN_PASSWORD` in `.env`, then restart the app.
- **Prediction says model unavailable:** check the server log for model loading or inference errors. Train a waste-specific classifier with the dataset under `trashnet-master/data/trashnet_cls/`, or configure a compatible checkpoint with `GEOSMART_MODEL_PATH`. The generic `yolo11n-cls.pt` base model is not a waste classifier.
- **PostgreSQL/PostGIS startup fails:** check the connection URL and ensure PostGIS is installed; SQLite needs no external database service.
- **Browser map/CDN assets do not load:** verify network access to the external CDN resources used by the templates.

## Deployment notes

The WSGI application is `geosmart.app:app`; on Linux platforms that install the production dependency, start with `gunicorn --workers 1 --bind 0.0.0.0:$PORT geosmart.app:app`. Configure secrets, database URL, and model path in the hosting environment. A single worker is recommended because training status and profile data are currently held in process memory.

SQLite, uploaded evidence, uploaded datasets, and trained weights require persistent storage in deployment. Use a persistent disk or managed database as appropriate. Image inference runs on CPU and can require substantial memory; test with the target model and hosting plan before deployment. This project has not been deployed to a hosting provider.
