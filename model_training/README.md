# Model Training Workspace

This folder is reserved for training models separately from the Flask app runtime files.

## Structure
- `datasets/` -> place your training datasets here
- `configs/` -> store training YAML/JSON configs
- `experiments/` -> training runs, logs, and metrics
- `weights/` -> final/best model files (`.pt`)

## Suggested flow
1. Put your dataset in `datasets/`
2. Add training config in `configs/`
3. Run training and save outputs to `experiments/`
4. Copy final best model to `weights/`

When you are ready, share the dataset/config details and I can wire a dedicated training command for you.
