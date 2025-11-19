# Converting to Production Scripts

## Convert training notebook
jupyter nbconvert --to python notebooks/train.ipynb --output ../scripts/train.py

## Convert inference notebook
jupyter nbconvert --to python notebooks/inference.ipynb --output ../scripts/inference.py
