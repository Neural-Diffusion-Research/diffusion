#!/usr/bin/env python
# -*- coding: utf-8 -*-

" rank module "

import os
import time
import argparse
import pickle
import numpy as np
from tqdm import tqdm
from dataset import Dataset
from knn import KNN
from diffusion import Diffusion
from sklearn import preprocessing
from evaluate import compute_map_and_print


def search():
    n_query = len(queries)
    diffusion = Diffusion(np.vstack([queries, gallery]), args.cache_dir)
    offline = diffusion.get_offline_results(args.truncation_size, args.kd)
    print(f'offline : {np.shape(offline)}')
    features = preprocessing.normalize(offline, norm="l2", axis=1)
    print(f'features : {np.shape(features)}')
    print(f'features[:n_query] : {np.shape(features[:n_query])}')
    print(f'features[n_query:].T : {np.shape(features[n_query:].T)}')
    scores = features[:n_query] @ features[n_query:].T
    print(f'scores : {np.shape(scores)}')
    ranks = np.argsort(-scores.todense())
    print(f'ranks : {np.shape(ranks)}')
    evaluate(ranks)


def search_old(gamma=3):
    diffusion = Diffusion(gallery, args.cache_dir)
    offline = diffusion.get_offline_results(args.truncation_size, args.kd)

    time0 = time.time()
    print('[search] 1) k-NN search')
    sims, ids = diffusion.knn.search(queries, args.kq)
    sims = sims ** gamma
    qr_num = ids.shape[0]

    print('[search] 2) linear combination')
    all_scores = np.empty((qr_num, args.truncation_size), dtype=np.float32)
    all_ranks = np.empty((qr_num, args.truncation_size), dtype=np.int)
    for i in tqdm(range(qr_num), desc='[search] query'):
        scores = sims[i] @ offline[ids[i]]
        parts = np.argpartition(-scores, args.truncation_size)[:args.truncation_size]
        ranks = np.argsort(-scores[parts])
        all_scores[i] = scores[parts][ranks]
        all_ranks[i] = parts[ranks]
    print('[search] search costs {:.2f}s'.format(time.time() - time0))

    # 3) evaluation
    evaluate(all_ranks)


def evaluate(ranks):
    gnd_name = os.path.splitext(os.path.basename(args.gnd_path))[0]
    with open(args.gnd_path, 'rb') as f:
        gnd = pickle.load(f)['gnd']
    compute_map_and_print(gnd_name.split("_")[-1], ranks.T, gnd)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache_dir',
                        type=str,
                        default='./cache',
                        help="""
                        Directory to cache
                        """)
    parser.add_argument('--dataset_name',
                        type=str,
                        required=True,
                        help="""
                        Name of the dataset
                        """)
    parser.add_argument('--query_path',
                        type=str,
                        required=True,
                        help="""
                        Path to query features
                        """)
    parser.add_argument('--gallery_path',
                        type=str,
                        required=True,
                        help="""
                        Path to gallery features
                        """)
    parser.add_argument('--gnd_path',
                        type=str,
                        help="""
                        Path to ground-truth
                        """)
    parser.add_argument('-n', '--truncation_size',
                        type=int,
                        default=1000,
                        help="""
                        Number of images in the truncated gallery
                        """)
    args = parser.parse_args()
    args.kq, args.kd = 10, 50
    return args


if __name__ == "__main__":
    args = parse_args()
    if not os.path.isdir(args.cache_dir):
        os.makedirs(args.cache_dir)
    dataset = Dataset(args.query_path, args.gallery_path)
    queries, gallery = dataset.queries, dataset.gallery
    print(f'queries : {np.shape(queries)}')
    print(f'gallery : {np.shape(gallery)}')
    search()

"""
queries : (55, 2048)
gallery : (5063, 2048)
diffusion : ()
[cache] loading ./tmp/oxford5k_resnet/offline.jbl costs 0.04s
offline : (5118, 5118)
features : (5118, 5118)
features[:n_query] : (55, 5118)
features[n_query:].T : (5118, 5063)
scores : (55, 5063)
ranks : (55, 5063)
>> oxford5k: mAP 93.10
"""
