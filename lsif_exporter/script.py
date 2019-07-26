import argparse
import time

from .consts import (EXPORTER_VERSION, PROTOCOL_VERSION)
from .export import export


def main():
    args = parse_args()
    start = time.time()

    with open(args.o, 'w+') as f:
        f.write(export(args.workspace))

    print('\nProcessed in {0:.2f}ms'.format((time.time() - start) * 1000))


def parse_args():
    parser = argparse.ArgumentParser(description='lsif-py is an LSIF exporter for Python.')
    parser.add_argument('workspace', help='set the path to the code, current directory by default')
    parser.add_argument('-o', help='change the output file, "data.lsif" by default', default='data.lsif')
    parser.add_argument('-v', '--version', action='version', version='Go LSIF exporter: {}, Protocol version: {}'.format(
        EXPORTER_VERSION,
        PROTOCOL_VERSION,
    ))

    return parser.parse_args()
