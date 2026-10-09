# Model weights

The application loads the trained Ultralytics waste-classification model from `waste_model.pt`, or from the location configured by `GEOSMART_MODEL_PATH`. Optional Keras weights can be configured with `GEOSMART_CNN_MODEL_PATH`. Weight files are intentionally excluded from Git.

The supplied checkout did not include a trained waste checkpoint. The local development copy now has `waste_model.pt`, generated from the six-class TrashNet dataset through `train_waste_model`; retrain it with the existing workflow when reproducing this setup. Keep the runtime weight file in persistent storage when deploying.
