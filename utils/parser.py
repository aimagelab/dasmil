import argparse


def get_args():
    parser = argparse.ArgumentParser(description='TRAIN DASMIL')
    group1=parser.add_argument_group("optimization")
    group1.add_argument('--lr', default=0.0002, type=float, help='learning rate')
    group1.add_argument('--weight_decay', default=0.005, type=float, help='Weight decay [5e-3]')

    group2=parser.add_argument_group("gnn")
    group2.add_argument('--residual', default=False, action="store_true",)
    group2.add_argument('--max', default=False, action="store_true")

    group2.add_argument('--num_layers', default=1, type=int, help='number of Graph layers')
    group2.add_argument('--dropout', default=True, action="store_true")
    group2.add_argument('--dropout_rate', default=0.2, type=float)
    group2.add_argument('--layer_name', default="GAT", type=str, help='layer graph name')
    group2.add_argument('--heads',default=3, type=int, help='layer graph name')


    group3=parser.add_argument_group("training")
    group3.add_argument('--seed', default=12, type=int, help='seed for reproducibility')
    group3.add_argument('--n_epoch', default=200, type=int, help='number of epochs')

    group4=parser.add_argument_group("dimensions")
    group4.add_argument('--n_classes', default=1, type=int, help='Number of output classes [2]')
    group4.add_argument('--c_hidden', default=256, type=int, help='intermediate size ')
    group4.add_argument('--input_size', default=384, type=int, help='input size ')

    group5= parser.add_argument_group("dataset")
    group5.add_argument('--scale', default="3", type=str, help='scale resolution')
    group5.add_argument('--dataset', default="cam", type=str,choices=["cam","lung"], help='input size ')
    group5.add_argument('--datasetpath',  type=str, help='dataset path')

    group6= parser.add_argument_group("distillation")
    group6.add_argument('--lamb', default=1, type=float, help='lambda')
    group6.add_argument('--beta', default=1, type=float, help='beta')
    group6.add_argument('--temperature', default=1.5, type=float, help='temperature')
    group6.add_argument('--add_bias', default=True,action="store_true")


    parser.add_argument('--tag', default="split", type=str, help='train strategy')
    parser.add_argument('--modeltype', default="WithGraph_y_Higher_kl_Lower", type=str, help='train strategy')
    parser.add_argument('--project', default="decider-geom", type=str, help='project name for wandb')
    parser.add_argument('--model', default="decider-geom", type=str, help='project name for wandb')
    parser.add_argument('--wandbname', default="main", type=str, help='project name for wandb')


    args = parser.parse_args()
    return args