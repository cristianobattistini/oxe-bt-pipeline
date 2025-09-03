import tensorflow_datasets as tfds
import numpy as np

ds, info = tfds.load("columbia_cairlab_pusht_real/0.1.0", split="train[:1%]", with_info=True, data_dir="/home/kcbat/tensorflow_datasets")
print("Available features:", info.features)

ex = next(iter(tfds.as_numpy(ds)))
print("Episode keys:", ex.keys())
print("Steps keys:", ex["steps"].keys())
