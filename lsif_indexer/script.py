import argparse
import time

from .consts import (INDEXER_VERSION, PROTOCOL_VERSION)
from .index import index


def main():
    args = parse_args()
    start = time.time()

    with open(args.o, 'w+') as f:
        index(args.workspace, f, args.verbose, args.exclude_content)

    print('\nProcessed in {0:.2f}ms'.format((time.time() - start) * 1000))


def parse_args():
    parser = argparse.ArgumentParser(description='lsif-py is an LSIF indexer for Python.')
    parser.add_argument('workspace', help='set the path to the code, current directory by default')
    parser.add_argument('-o', help='change the output file, "data.lsif" by default', default='data.lsif')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output verbose logs', default=False)
    parser.add_argument('--exclude-content', action='store_true', help='Do not emit document content', default=False)
    parser.add_argument('--version', action='version', version='Go LSIF indexer: {}, Protocol version: {}'.format(
        INDEXER_VERSION,
        PROTOCOL_VERSION,
    ))

    return parser.parse_args()
