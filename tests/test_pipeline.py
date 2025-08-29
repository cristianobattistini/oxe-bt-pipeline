import datasets

# Load a specific sub-dataset in streaming mode
ds = datasets.load_dataset("jxu124/OpenX-Embodiment", "fractal20220817_data", streaming=True, split='train')

# You can now iterate through the dataset
for episode in ds:
    # 'episode' will be a dictionary containing the trajectory data
    print(episode)
    break 
