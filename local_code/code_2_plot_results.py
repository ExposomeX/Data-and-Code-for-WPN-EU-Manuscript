"""2. Draw all submitted chemicals: BEQ bars and cumulative contribution."""
import argparse
import csv
from pathlib import Path
from wpn_core import CSV_COLUMNS, environment

def plot(result_file):
    handles = environment()
    import matplotlib.pyplot as plt
    import numpy as np
    with Path(result_file).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('The result table contains no chemicals.')
    names = [row['Chemical'] for row in rows]
    values = [float(row[CSV_COLUMNS[3]]) for row in rows]
    cumulative = np.cumsum([float(row[CSV_COLUMNS[4]]) for row in rows])
    for scale in ['log', 'linear']:
        width = max(8., min(32., len(rows) * .52 + 3.))
        fig, axis = plt.subplots(figsize=(width, 7.8), layout='constrained')
        x = np.arange(len(rows))
        axis.bar(x, values, color='#3864d9', width=.72, zorder=3)
        axis.set_yscale(scale)
        axis.set_ylabel('BEQ (μg/L Narciclasine-EQ)')
        axis.set_xlabel('Chemical')
        axis.set_xticks(x, names, rotation=65, ha='right', fontsize=8)
        axis.grid(axis='y', alpha=.25, zorder=0)
        axis.spines[['top']].set_visible(False)
        if scale == 'log':
            axis.set_ylim(min(values) * .5, max(values) * 2.)
        right = axis.twinx()
        right.plot(x, cumulative, color='#e49336', marker='o', markersize=3, linewidth=1.6, label='Cumulative contribution')
        right.set_ylim(0, 105)
        right.set_yticks([0,20,40,60,80,100])
        right.set_ylabel('Cumulative contribution (%)')
        right.spines['top'].set_visible(False)
        right.legend(loc='upper left', frameon=False)
        axis.set_title(f'WPN results · {len(rows)} chemicals', loc='left', weight='bold')
        output = Path(result_file).with_name(f'WPN_BEQ_{scale}.png')
        fig.savefig(output, dpi=300, facecolor='white')
        plt.close(fig)
    return Path(result_file).with_name('WPN_BEQ_log.png')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_file', type=Path)
    plot(parser.parse_args().result_file)
