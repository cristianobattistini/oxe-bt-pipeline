import tensorflow as tf
import os

def load_examples_from_tfrecords(files, take=1):
    """
    Carica record grezzi dai file TFRecord specificati.
    """
    dataset = tf.data.TFRecordDataset(files)
    for i, record in enumerate(dataset.take(take)):
        print(f"[Record {i}] size={len(record.numpy())} bytes")
        yield record

if __name__ == "__main__":
    base = r"C:\Users\Crist\tensorflow_datasets\language_table\0.0.1"
    files = [
        os.path.join(base, "language_table-train.tfrecord-00005"),
        os.path.join(base, "language_table-train.tfrecord-00024"),
    ]
    for rec in load_examples_from_tfrecords(files, take=3):
        pass
