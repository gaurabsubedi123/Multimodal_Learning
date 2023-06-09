# -*- coding: utf-8 -*-
"""preparations.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1aICtFqbgA11_kaRG5VrMCdN8rQF2cWnd

# Data Preparations

This notebook goes through the various steps to prepare the data from .csv files to PyTorch Training, Validation,
and Test Datasets and Dataloaders.

In addition, the ChexNet pre-trained weights that we used had to be processed to be compatible with the current
PyTorch architecture. This processing step, which only has to be done once, re-saves the pre-trained weights in a
format that can be readily loaded in the current PyTorch version (1.7.0).

## Importing Required Libraries
"""

import os
from pathlib import Path
import json
import torch
import torch.nn as nn
import torchvision
import re
import pandas as pd
import csv
from sklearn.model_selection import train_test_split


"""
# Checking the Current PyTorch Version
"""

print(f'Current PyTorch version: {torch.__version__}')

"""
## Data Sharing

We have made the datasets we used in our baseline experiments available via a shared Google Drive as mentioned in the 
project README. 

It is not necessary to re-run the scripts to generate the prepared datasets.  

However, if you wish, the prepared datasets can be recreated by running this script in the /data/ directory of the
project.

### Data Files Organization

* All the original .csv files are in the **'image_labels_csv'** directory. These various csv files are variations of 
the original dataset in terms of which metadata field(s) we use for the text modality. 

* There are 2 metadata fields we consider: 
    * 'findings'
    * 'impression'.  


* In Chest X-Ray reporting, in addition to the actual X-ray image, radiologists usually report their 'read' by 
describing the findings and their determination of the findings. The findings and determination are summarized in the 
'findings' and 'impression' fields respectively. 

* All the Train, Validation, and Test partitions are saved in their respective directories: **'json'** for the .jsonl 
files and **'csv'** for the .csv files. 

* The saved ChexNet pre-trained weights, both the outdated .pth.tar and current .pt versions are in the 'models' 
directory. 

### JSONL Files

The MMBT JsonlDataset(Dataset) Class, which prepares the input dataset for generating batches for the model expects 
the data in a .jsonl file format. 

The 'create_jsonl_data' function converts a 'json dict' object to a specified data directory and jsonl filename.
"""


def create_jsonl_data(data_dir, jsonl_filename, json_dict):
    with open(os.path.join(data_dir, jsonl_filename), "w") as fw:
        data_obj = {}
        for idx, data_dict in json_dict.items():
            data_obj['id'] = idx
            for key, value in data_dict.items():
                data_obj[key] = value
            fw.write("%s\n" % json.dumps(data_obj))


"""
### .CSV Files

The text and image only models do not need the data to be in the .jsonl file format.  

The 'creat_csv_data' simply saves a Pandas dataframe to a specified data directory and csv filename.
"""


def create_csv_data(data_dir, csv_filename, df):
    df.to_csv(path_or_buf=os.path.join(data_dir, csv_filename))


"""
### Train, Validation, and Test Set Partitioning

We partition all the original csv files into a 60/20/20 Train/Validation/Test partitions.  

We use the standard *sklearn train_test_split* function with the specified *random_state = 1* to create the 
partitions with reproducibility. 

#### Specifying Directory Names

These are where the current original csv and prepared jsonl and csv datasets are stored in the shared drive.
"""
try:
    FILE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError('So, __file__ does not exist?'):
    FILE_DIR = Path().resolve()

ORIG_DATA_DIR = 'image_labels_csv'
JSON_DIR = 'json'
CSV_DIR = 'csv'

# Load the datasets into a pandas dataframe.
csv_files = []
path = os.path.join(FILE_DIR, ORIG_DATA_DIR)
for filename in os.listdir(path):
    name = filename.partition('.')[0]
    df = pd.read_csv(os.path.join(path, filename))
    df = df.rename(columns={"Filename": "img", "Label": "label", "LabelText": "text"})
    csv_files.append((name, df))

# Report the number of sentences and print out the first few examples.
for df in csv_files:
    print(f'Number of training sentences in {df[0]}: {df[1].shape[0]:,}\n')
    print(f'{df[1].head()}\n')

# Split dataframes into train/val/test and create jsonl/csv files from splits.
for df in csv_files:
    train, test = train_test_split(df[1], test_size=0.2, random_state=1)

    # 0.25 * 0.8 = 0.2
    # end result: 60/20/20 train/val/test splits
    train, val = train_test_split(train, test_size=0.25, random_state=1)

    # csv files
    create_csv_data(CSV_DIR, df[0] + '_train.csv', train)
    create_csv_data(CSV_DIR, df[0] + '_val.csv', val)
    create_csv_data(CSV_DIR, df[0] + '_test.csv', test)

    # jsonl files
    train_json_str = train.to_json(orient="index")
    train_df_json = json.loads(train_json_str)

    val_json_str = val.to_json(orient='index')
    val_df_json = json.loads(val_json_str)

    test_json_str = test.to_json(orient='index')
    test_df_json = json.loads(test_json_str)

    create_jsonl_data(JSON_DIR, df[0] + '_train.jsonl', train_df_json)
    create_jsonl_data(JSON_DIR, df[0] + '_val.jsonl', val_df_json)
    create_jsonl_data(JSON_DIR, df[0] + '_test.jsonl', test_df_json)

"""
## ChexNet Saved Pre-Trained Weight

For convenience, we did not re-implement nor re-trained the ChexNet experiment to obtain the weight, but we used the 
weights from the following PyTorch implementation: https://github.com/arnoweng/CheXNet. 

### Specifying Directories and ChexNet parameters
"""

SAVED_MODELS_DIR = 'models'
CKPT_PATH = os.path.join(SAVED_MODELS_DIR, 'model.pth.tar')
N_CLASSES = 14


class DenseNet121(nn.Module):
    """Model modified.

    The architecture of our model is the same as standard DenseNet121
    except the classifier layer which has an additional sigmoid function.

    """

    def __init__(self, out_size):
        super(DenseNet121, self).__init__()
        self.densenet121 = torchvision.models.densenet121(pretrained=True)
        num_ftrs = self.densenet121.classifier.in_features
        self.densenet121.classifier = nn.Sequential(
            nn.Linear(num_ftrs, out_size),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.densenet121(x)
        return x


# initialize and load the model
# comment out .cuda for when using the weights as part of MMBT
model_ft = DenseNet121(N_CLASSES)  # .cuda()

# since the pickled pretrained model was created using a much older version of
# pytorch we need to reformat the file a bit to be able to open it with current
# pytorch version.
if os.path.isfile(CKPT_PATH):
    print("=> loading checkpoint")
    checkpoint = torch.load(CKPT_PATH, map_location=torch.device('cpu'))
    state_dict = checkpoint['state_dict']
    remove_data_parallel = True
    pattern = re.compile(
        r'^(.*denselayer\d+\.(?:norm|relu|conv))\.((?:[12])\.(?:weight|bias|running_mean|running_var))$')

    for key in list(state_dict.keys()):
        match = pattern.match(key)
        new_key = match.group(1) + match.group(2) if match else key
        new_key = new_key[7:] if remove_data_parallel else new_key
        state_dict[new_key] = state_dict[key]
        # Delete old key only if modified.
        if match or remove_data_parallel:
            del state_dict[key]

    model_ft.load_state_dict(state_dict)
    print("=> loaded checkpoint")
else:
    print("=> no checkpoint found")

torch.save(model_ft.densenet121, os.path.join(SAVED_MODELS_DIR, 'saved_chexnet.pt'))
print('Model saved.')
