#!/usr/bin/env python3

import argparse
import pathlib
import sys

from . import download, merge
from .utils import logger, increase_logging_verbosity
from .version import __version__


def main():
    parser = argparse.ArgumentParser()
    add = parser.add_argument
    add('m3u8_url',
        help='the VOD URL')
    add('output', type=pathlib.Path,
        help='path to the final output file')
    add('-f', '--force', action='store_true',
        help='overwrite the output file if it already exists')
    add('-j', '--jobs', type=int, default=None,
        help='''maximum number of concurrent downloads (default is twice
        the number of CPU cores, including virtual cores)''')
    add('-v', '--verbose', action='count', default=0,
        help='increase logging verbosity (can be specified multiple times)')
    add('-q', '--quiet', action='count', default=0,
        help='decrease logging verbosity (can be specified multiple times)')
    add('-V', '--version', action='version', version=__version__)
    args = parser.parse_args()

    if args.jobs is not None and args.jobs <= 0:
        logger.critical('jobs must be positive')
        return 1

    if not args.output.parent.exists():
        logger.critical(f'{args.output.parent} does not exist')
        return 1

    if not args.output.suffix:
        logger.critical(f'output must have a suffix, e.g., .mp4')
        return 1

    if args.output.exists() and not args.force:
        logger.critical(f'{args.output} already exists; specify --force to overwrite it')
        return 1

    increase_logging_verbosity(args.verbose - args.quiet)

    remote_m3u8_url = args.m3u8_url
    working_directory = args.output.with_suffix('')
    working_directory.mkdir(exist_ok=True)
    remote_m3u8_file = working_directory / 'remote.m3u8'
    local_m3u8_file = working_directory / 'local.m3u8'
    try:
        if not download.download_m3u8_file(remote_m3u8_url, remote_m3u8_file):
            logger.critical(f'failed to download {remote_m3u8_url}')
            return 1
        logger.info(f'downloaded {remote_m3u8_file}')
        if not download.download_m3u8_segments(remote_m3u8_url,
                                               remote_m3u8_file,
                                               local_m3u8_file,
                                               jobs=args.jobs):
            logger.critical('failed to download some segments')
            return 1
        merge.incremental_merge(local_m3u8_file, args.output)
    except RuntimeError as e:
        logger.critical(e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
