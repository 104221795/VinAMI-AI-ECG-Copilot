# VinStroke-ECG

Cloud-ready research pipeline for **hierarchical / multi-label 12-lead ECG interpretation** using PTB-XL and time-frequency vision models.

Core scope:

- Dataset: PTB-XL
- Task: multi-label classification of 5 diagnostic superclasses
  - `NORM`
  - `MI`
  - `STTC`
  - `CD`
  - `HYP`
- Representations:
  - CWT scalogram 12-lead grid
  - STFT spectrogram 12-lead grid
- Models:
  - ResNet18 baseline
  - ConvNeXt-Tiny main vision baseline

The local machine does not need a GPU. Run data generation/training on Colab or Kaggle.

## Colab/Kaggle quick start

```bash
pip install -r requirements-colab.txt
```

Download PTB-XL 100 Hz in the cloud runtime:

```bash
python src/download_ptbxl.py --sampling 100 --output data/ptb-xl
```

Create the 5-superclass multi-label manifest:

```bash
python src/prepare_ptbxl_superclass_manifest.py --ptbxl-root data/ptb-xl --output data/ptbxl_superclass_manifest.csv
```

Generate a small CWT image set first:

```bash
python src/build_ptbxl_tf_grids.py --ptbxl-root data/ptb-xl --manifest data/ptbxl_superclass_manifest.csv --outdir data/ptbxl_images_cwt --representation cwt --limit 2000
```

Train a baseline:

```bash
python src/train_multilabel_vision.py --manifest data/ptbxl_images_cwt/manifest_images.csv --model resnet18 --epochs 5 --batch-size 32
```

Train the stronger model:

```bash
python src/train_multilabel_vision.py --manifest data/ptbxl_images_cwt/manifest_images.csv --model convnext_tiny --epochs 15 --batch-size 32
```

## Split

PTB-XL recommended split:

- folds 1-8: train
- fold 9: validation
- fold 10: test

Do not random-split images, because that can cause patient/record leakage.

