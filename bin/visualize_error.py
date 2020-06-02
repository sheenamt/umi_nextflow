#!/usr/bin/env python3
"""
Script to visualize non-reference reads in a set of files created by VarScan readcounts
"""
import os
import argparse 
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

BASES = ['A', 'C', 'G', 'T']

def build_parser(parser):
    parser.add_argument('readcounts', nargs='+',
        help='Output from mpileup2readcounts')
    parser.add_argument('-o', '--outpath',
        help='Path prefix for output files')
    parser.add_argument('-l', '--labels', nargs='+',
        help='Labels for chart titles')


# older version that created dataframe from output of VarScan readcounts
def VARSCAN_readcounts_to_dataframe(readcounts):
    with open(readcounts, 'r') as f:
        series_list = []
        print(datetime.now(), "reading from readcounts")
        header = next(f)
        for line in f:
            row_fields = line.strip().split('\t')
            s_dict = {}
            s_dict['chrom'] = row_fields[0]
            s_dict['pos'] = int(row_fields[1])
            s_dict['ref'] = row_fields[2]
            s_dict['depth'] = int(row_fields[4])
            
            for entry in row_fields[5:]:
                entry_fields = entry.split(':')
                base = entry_fields[0]
                if base in BASES:
                    s_dict[base] = int(entry_fields[1])

            series_list.append(pd.Series(s_dict))

    print(datetime.now(), "file read")

    df = pd.concat(series_list, axis=1).T
    df.fillna(0, inplace=True)

    for base in BASES:
        df[base + '_freq'] = df[base] / df['depth']

    df.set_index(['chrom', 'pos'], inplace=True)
    print(datetime.now(), "dataframe constructed")
    return df

# current version uses output from mpileup2readcounts binary
def readcounts_to_dataframe(readcounts):
    col_names = ['chrom', 'pos', 'ref', 'depth', 'A', 'T', 'C', 'G', 'a', 't', 'c', 'g', 'ins', 'del', 'empty']
    df = pd.read_csv(readcounts, sep='\t', header=0, names=col_names, dtype={'chrom' : str})

    for base in BASES:
        df[base] = df[base] + df[base.lower()]
        df[base + '_freq'] = df[base] / df['depth']

    df.set_index(['chrom', 'pos'], inplace=True)
    return df

def create_vaf_histogram(df, title, axis):
    # create array of every non-zero VAF
    vaf_list = []
    for ref in BASES:
        ref_df = df[df['ref'] == ref]
        for var in [x for x in BASES if x != ref]:
            var_df = ref_df[ref_df[var + '_freq'] > 0]
            vaf_list.append(var_df[var + '_freq'].ravel())

    vafs = np.concatenate(vaf_list)

    # generate histogram
    axis.hist(vafs, bins=np.arange(0, 1.001, 0.005), log=True)
    axis.set_title(title)
    axis.set_xlabel('non-reference read franction')

def create_error_heatmap(df, title, axis):
    
    # calculate error rates
    error_rates = pd.DataFrame(columns=BASES, index=pd.Series(BASES, name='ref'))
    for ref in BASES:
        ref_df = df[df['ref'] == ref]
        for var in BASES:
            ref_reads = ref_df['depth'].sum()
            try:
                error_rates.loc[ref, var] = ref_df[var].sum() / ref_reads
            except ZeroDivisionError:
                continue
    
    # plot heatmap of log-adjusted errors for better contrast
    log_matrix = np.log10(error_rates.to_numpy(dtype=np.float64))
    axis.imshow(log_matrix, cmap='cool')

    # add axis ticks and labels
    ref_bases = error_rates.index
    var_bases = error_rates.columns
    axis.set_title(title)
    axis.set_xlabel('ALT Base')
    axis.set_xticks(range(len(var_bases)))
    axis.set_xticklabels(var_bases)
    axis.set_xlim(-0.5, len(var_bases) - 0.5)
    axis.set_ylabel('REF Base')
    axis.set_yticks(range(len(ref_bases)))
    axis.set_yticklabels(ref_bases)
    axis.set_ylim(len(ref_bases) - 0.5, -0.5)

    # add text to each grid square with the non-log error rate
    for i in range(len(ref_bases)):
        for j in range(len(var_bases)):
            value = round(error_rates.iloc[i, j], 5)
            text = axis.text(j, i, value, ha="center", va="center", color="black")

if __name__ == '__main__':
    # parse the args
    parser = argparse.ArgumentParser()
    build_parser(parser)
    args = parser.parse_args()

    num_files = len(args.readcounts)

    if args.labels:
        labels = args.labels
    else:
        labels = ["plot {}".format(i + 1) for i in range(num_files)]

    # create multi-histogram
    hist_fig, hist_axs = plt.subplots(1, num_files, sharey='row', figsize=(num_files*4 + 2, 6))
    heat_fig, heat_axs = plt.subplots(1, num_files, figsize=(num_files*4 + 2, 6))

    try:
        for rc, l, hist_ax, heat_ax in zip(args.readcounts, labels, hist_axs, heat_axs):
            # convert the readcounts file to a dataframe
            df = readcounts_to_dataframe(rc)
            # create histogram of non-reference VAFs
            create_vaf_histogram(df, l, hist_ax)
            # create heatmap of base conversion rates
            create_error_heatmap(df, l, heat_ax)

    # if only one readcounts file is provided    
    except TypeError:
        df = readcounts_to_dataframe(args.readcounts[0])
        l = labels[0]
        create_vaf_histogram(df, l, hist_axs)
        create_error_heatmap(df, l, heat_axs)
    
    hist_fig.tight_layout()
    hist_fig.savefig(args.outpath + '.VAFs.png')

    heat_fig.tight_layout()
    heat_fig.savefig(args.outpath + '.error_rates.png')