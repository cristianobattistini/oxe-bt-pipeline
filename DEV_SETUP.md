## Setup Instructions

This project uses [Conda](https://docs.conda.io/en/latest/miniconda.html) to manage dependencies. Follow these steps to create a consistent and isolated environment.

### 1. Prerequisite: Install Conda

If you don't have Conda installed, download and install **Miniconda** (a lightweight version of Anaconda) for your operating system from the [official website](https://docs.conda.io/en/latest/miniconda.html).

### 2. Create the Conda Environment

Navigate to the project's root directory (where the `environment.yml` file is located) in your terminal and run the following command. This will create a new environment named `oxe-bt-pipeline` with all the necessary packages.

```bash
conda env create -f environment.yml
```
This process might take a few minutes as Conda resolves and downloads the dependencies.

### 3. Activate the Environment

Before running any scripts, you must **activate** the environment. This makes the project's specific Python interpreter and packages available in your terminal session.

```bash
conda activate oxe-bt-pipeline
```
You'll know it's active because your terminal prompt will be prefixed with `(oxe-bt-pipeline)`.

### 4. Verify the Installation

To ensure everything is installed correctly, you can list the installed packages:

```bash
conda list pydantic
```
This should show you that the `pydantic` package is installed.

### Deactivating the Environment

When you're finished working on the project, you can deactivate the environment to return to your base terminal configuration:

```bash
conda deactivate
```