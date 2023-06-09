import tqdm
import vision_transformer as vits
import numpy as np
import pandas as pd
import sys
import argparse
import os
import glob
import copy
import torchvision.transforms.functional as VF
import torch.nn as nn
import torch
from joblib import dump
from torchvision import models as torchvision_models
from collections import OrderedDict
from PIL import Image
import utils as utils


sys.path.append(os.environ["DINO_REPO"])

# Extract x and y coordinates from patch path


def getinfo(patch):

    infos = patch.split(os.sep)[-1].split("_")
    y = int(infos[-1].split(".")[0])
    x = int(infos[-3])
    return x, y

# Encapsulate patch information into a dictionary


def encapsulate_patch_info(parent_id, x, y, id, shift, level, embedding, path):
    kinfo = {}
    kinfo["childof"] = parent_id
    kinfo["x"] = x
    kinfo["id"] = id
    kinfo["y"] = y
    kinfo["shift"] = shift
    kinfo["level"] = level
    kinfo["embedding"] = embedding
    kinfo["path"] = path
    return kinfo

# Get the embedding for an image patch from the specified resolution level of the models


def getembedding(models, img, level):
    level = 3-level
    # img = Image.open(path)
    img = VF.to_tensor(img).float().cuda()
    img = img.view(1, 3, 256, 256)
    embedding = models[level](img).detach().cpu().numpy()
    return embedding

# Get properties of a candidate from a CSV file


def properties(candidate, path):
    df = pd.read_csv(path)
    row = df.iloc[candidate]
    real_name = row["image"]
    label = row["label"]
    test = row["phase"]
    down = 0
    return real_name, id, label, test, down

 # Check the entropy of an image to determine its quality


def checkentropy(image):
    if image.entropy() < 5:
        return False
    else:
        return True


# Recursively get children patches and their embeddings


def get_children(parent_id, x_base, y_base, basepath, allowedlevels, level, models, kinfos, infosConcat, base_shift):
    # if no children return list unchanged
    if level == 4:
        return kinfos, infosConcat
    # calcolate children coordinates
    shift = int(base_shift/2**level)
    upperleft = (x_base, y_base)
    lowleft = (x_base, y_base+shift)
    upperright = (x_base+shift, y_base)
    lowright = (x_base+shift, y_base+shift)
    if parent_id is not None:
        parent = kinfos[parent_id]
    for patch in [upperleft, lowleft, upperright, lowright]:
        x, y = patch
        path = glob.glob(os.path.join(
            basepath, "*_x_"+str(x)+"_y_"+str(y)+".jpg"))
        # if file is not present continue
        if len(path) == 0:
            continue
        path = path[0]
        image = Image.open(path)
        if level in allowedlevels and checkentropy(image):
            x, y = getinfo(path)
            embedding = getembedding(models, image, level)
            if parent_id is not None:
                concatened = np.concatenate(
                    [parent["embedding"], embedding], axis=-1)
                infosConcat.extend(concatened)
            kinfo = encapsulate_patch_info(parent_id=parent_id, x=x, y=y, id=len(
                kinfos), shift=shift, level=level, embedding=embedding, path=path)
            kinfos.append(kinfo)
            kinfos, infosConcat = get_children(kinfo["id"], x, y, path.split(
                ".")[0], allowedlevels, level+1, models, kinfos, infosConcat, base_shift)
        else:
            kinfos, infosConcat = get_children(parent_id, x, y, path.split(
                ".")[0], allowedlevels, level+1, models, kinfos, infosConcat, base_shift)

    return kinfos, infosConcat

  # Search for neighboring patches and add the information to the DataFrame


def search_neighboors(infos):
    df = pd.DataFrame(infos)
    df["nearsto"] = None
    print("scanning for neighboors")
    for level in tqdm.tqdm(range(0, 4)):
        df2 = df[df["level"] == level]
        for idx in range(df2.shape[0]):
            patch = df2.iloc[idx]
            shift = patch["shift"]
            x = patch["x"]
            y = patch["y"]
            lista = []
            df3 = df2.query("(x=="+str(x+shift)+" & y=="+str(y)+") | (x=="+str(x+shift)+" & y=="+str(y + shift)+") | (x=="+str(x)+" & y=="+str(y+shift)+")  | (x=="+str(x-shift)+" & y=="+str(
                y+shift)+")  | (x=="+str(x-shift)+" & y=="+str(y)+")  | (x=="+str(x-shift)+" & y=="+str(y-shift)+")  | (x=="+str(x)+" & y=="+str(y-shift)+")  | (x=="+str(x+shift)+" & y=="+str(y-shift)+")")
            for idx2 in range(df3.shape[0]):
                neighboor = df3.iloc[idx2]
                lista.append(neighboor["id"])
            df.at[df.index[df["id"] == patch["id"]][0], "nearsto"] = lista
    return df

 # Create an adjacency matrix based on the neighboring patches


def create_matrix(df):
    matrix = torch.zeros(size=[df.shape[0], df.shape[0]])
    for idx in range(df.shape[0]):
        patch = df.iloc[idx]
        i = patch["id"]
        neighbors = patch["nearsto"]
        parent = patch["childof"]
        for j in neighbors:
            matrix[int(i), int(j)] = 1
            matrix[int(j), int(i)] = 1
        if parent is not None:
            if not np.isnan(parent):
                matrix[int(i), int(parent)] = 1
                matrix[int(parent), int(i)] = 1
    return matrix

# Compute tree features for a slide


def compute_tree_feats_Slide(real_name, label, test, args, models, save_path=None, base_shift=2048):
    allowedlevels = args.levels
    level = 1
    shift = int(base_shift/2**level)
    with torch.no_grad():
        # initialize list
        torch.backends.cudnn.enabled = False
        infos = []
        infos_concat = []
        dest = os.path.join(save_path, test, real_name+"_"+str(label))
        low_patches = glob.glob(os.path.join(
            args.extractedpatchespath, real_name, '*.jpg'))
        for path in tqdm.tqdm(low_patches):
            # extract info about patch
            x, y = getinfo(path)
            if level in allowedlevels:
                embedding = getembedding(models, path, level)
                kinfo = encapsulate_patch_info(parent_id=None, path=path, x=x, y=y, id=len(
                    infos), shift=shift, level=level, embedding=embedding)
                infos.append(kinfo)
                infos, infos_concat = get_children(kinfo["id"], x, y, path.split(
                    ".")[0], args.levels, level+1, models, infos, infos_concat, base_shift)
            else:
                infos, infos_concat = get_children(None, x, y, path.split(
                    ".")[0], args.levels, level+1, models, infos, infos_concat, base_shift)
        # infos should contain list of dicts per patch
        infos = search_neighboors(infos)
        matrix = create_matrix(infos)
        os.makedirs(dest, exist_ok=True)

        dump(infos, os.path.join(dest, "embeddings.joblib"))
        torch.save(matrix, os.path.join(dest, "adj.th"))
        del infos
# Load parameters for a model


def load_parameters(model, path, name, device):
    state_dict_weights = torch.load(path, map_location=device)
    for i in range(4):
        state_dict_weights.popitem()
    state_dict_init = model.state_dict()
    new_state_dict = OrderedDict()
    for (k, v), (k_0, v_0) in zip(state_dict_weights.items(), state_dict_init.items()):
        name = k_0
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict, strict=False)
    return model


def main():
    parser = argparse.ArgumentParser(
        description='Compute features from DINO embedder')
    parser.add_argument('--num_workers', default=4, type=int,
                        help='Number of threads for datalodaer')
    parser.add_argument('--norm_layer', default='instance',
                        type=str, help='Normalization layer [instance]')
    parser.add_argument("--extractedpatchespath",
                        default="HIERARCHICALSOURCEPATH", type=str)
    parser.add_argument("--savepath", type=str, default="DESTINATIONPATH")
    parser.add_argument("--job_number", type=int, default=-1)
    parser.add_argument('--arch', default='vit_small',
                        type=str, help='Architecture')
    parser.add_argument('--patch_size', default=16, type=int,
                        help='Patch resolution of the model.')
    parser.add_argument('--pretrained_weights1', default='CHECKPOINTDINO20x',
                        type=str, help="embedder trained at level 1 (scale x20).")
    parser.add_argument('--pretrained_weights2', default='CHECKPOINTDINO10x',
                        type=str, help="embedder trained at level 2 (scale x10)")
    parser.add_argument('--pretrained_weights3', default='CHECKPOINTDINO5x',
                        type=str, help="embedder trained at level 3 (scale x5).")
    parser.add_argument('--n_last_blocks', default=4, type=int,
                        help="""Concatenate [CLS] tokens for the `n` last blocks. We use `n=4` when evaluating ViT-Small and `n=1` with ViT-Base.""")
    parser.add_argument('--avgpool_patchtokens', default=False, type=utils.bool_flag,
                        help="""Whether ot not to concatenate the global average pooled features to the [CLS] token.
        We typically set this to False for ViT-Small and to True with ViT-Base.""")
    parser.add_argument("--checkpoint_key", default="teacher", type=str,
                        help='Key to use in the checkpoint (example: "teacher")')
    args = parser.parse_args()
    model = buildnetwork(args)
    # ============ building network ... ============

    models = []
    weights = [args.pretrained_weights1,
               args.pretrained_weights2, args.pretrained_weights3]
    for idx in range(3):
        net = copy.deepcopy(model)
        net = net.cuda()
        net.eval()
        utils.load_pretrained_weights(
            net, weights[idx], args.checkpoint_key, args.arch, args.patch_size)
        models.append(net)

    print(f"Model {args.arch} built.")
    print('Use pretrained features.')
    bags_path = os.path.join(args.extractedpatchespath, "*")
    feats_path = args.savepath
    os.makedirs(feats_path, exist_ok=True)
    bags_list = glob.glob(bags_path)
    num_bags = len(bags_list)
    for slideNumber in range(num_bags):
        compute_tree_feats_Slide(
            slideNumber, args, bags_list, models, feats_path)


def processSlide(start, args):
    model = buildnetwork(args)
    models = []
    weights = [args.pretrained_weights1,
               args.pretrained_weights2, args.pretrained_weights3]
    for idx in range(3):
        net = copy.deepcopy(model)
        net = net.cuda()
        net.eval()
        if args.model == "dino":
            utils.load_pretrained_weights(
                net, weights[idx], args.checkpoint_key, args.arch, args.patch_size)
        models.append(net)
    print('Use pretrained features.')
    # bags_path = os.path.join(args.extractedpatchespath,"*")
    feats_path = args.savepath
    os.makedirs(feats_path, exist_ok=True)
    # bags_list = glob.glob(bags_path)
    for slideNumber in range(start, start+args.step):
        real_name, id, label, test, down = properties(
            slideNumber, args.propertiescsv)

        if os.path.isfile(os.path.join(feats_path, test, real_name+"_"+str(label), "embeddings.joblib")):
            print("skip")
            continue
        elif test != "test":
            continue
        else:
            compute_tree_feats_Slide(
                real_name, label, test, args, models, feats_path, 4096/(1+down))


def buildnetwork(args):
    # ============ building network ... ============
    # if the network is a Vision Transformer (i.e. vit_tiny, vit_small, vit_base)
    if args.model == "dino":
        if args.arch in vits.__dict__.keys():
            model = vits.__dict__[args.arch](
                patch_size=args.patch_size, num_classes=0)
            embed_dim = model.embed_dim * \
                (args.n_last_blocks + int(args.avgpool_patchtokens))
        # if the network is a XCiT
        elif "xcit" in args.arch:
            model = torch.hub.load(
                'facebookresearch/xcit:main', args.arch, num_classes=0)
            embed_dim = model.embed_dim
        # otherwise, we check if the architecture is in torchvision models
        elif args.arch in torchvision_models.__dict__.keys():
            model = torchvision_models.__dict__[args.arch]()
            embed_dim = model.fc.weight.shape[1]
            model.fc = nn.Identity()
        else:
            print(f"Unknow architecture: {args.arch}")
            sys.exit(1)
        return model


if __name__ == '__main__':
    main()
