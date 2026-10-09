# Model training resources

The Flask application uses Ultralytics for classification training and writes new runs to `ml/runs/`. The training helpers are in `ml/training/scripts/` and use repository-root-relative paths, so they work when launched from another current directory.

## Prepare the TrashNet classification dataset

The source images are retained in `trashnet-master/data/dataset-resized/`. To regenerate the train/validation/test split:

```powershell
py -3.14 ml/training/scripts/prepare_trashnet_cls.py
```

The script rebuilds `trashnet-master/data/trashnet_cls/` and writes its `data.yaml`. It removes any current prepared split before copying, so back up local edits to that generated directory first. The optional small-sample script similarly rebuilds `trashnet_cls_tiny/`:

```powershell
py -3.14 ml/training/scripts/make_tiny_cls_subset.py
```

## Train in the application

Configure `ADMIN_PASSWORD` in `.env`, open `/admin/login`, then use the training panel on the Analyze page. Provide the path to the prepared dataset or its YAML file. New training run records are stored in `ml/runs/`; the best weights are copied to `models/waste_model.pt` for inference.

Training downloads the Ultralytics base weights on first use if they are not already present. Training was not run during project verification. The checked-in `ml/runs/` contents are historical plots, metrics, and configuration only; there are no trained checkpoints in the supplied project.

## Preserved notebook

`notebooks/garbage-classification-using-cnn.ipynb` is a historical standalone Keras experiment. The web application does not require it or a TensorFlow installation. If you provide a compatible `.h5` model, set `GEOSMART_CNN_MODEL_PATH` to enable that optional inference path.
