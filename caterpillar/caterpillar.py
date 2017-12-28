#!/usr/bin/env python3

import argparse
import pathlib
import shutil
import sys
import urllib.parse

from . import download, merge
from .utils import excname, logger, increase_logging_verbosity
from .version import __version__


def main():
    parser = argparse.ArgumentParser()
    add = parser.add_argument
    add('m3u8_url',
        help='the VOD URL')
    add('output', nargs='?', type=pathlib.Path, default=None,
        help='''path to the final output file (default is a .ts file in the
        current directory with the basename of the VOD URL)''')
    add('-f', '--force', action='store_true',
        help='overwrite the output file if it already exists')
    add('-j', '--jobs', type=int, default=None,
        help='''maximum number of concurrent downloads (default is twice
        the number of CPU cores, including virtual cores)''')
    add('-k', '--keep', action='store_true',
        help='keep intermediate files even after a successful merge')
    add('-m', '--concat-method',
        choices=['concat_demuxer', 'concat_protocol', '0', '1'],
        default='concat_demuxer',
        help='''method for concatenating intermediate files (default is
        'concat_demuxer'); see https://github.com/zmwangx/caterpillar/#notes
        for details''')
    add('--wipe', action='store_true',
        help='wipe all downloaded files (if any) and start over')
    add('-v', '--verbose', action='count', default=0,
        help='increase logging verbosity (can be specified multiple times)')
    add('-q', '--quiet', action='count', default=0,
        help='decrease logging verbosity (can be specified multiple times)')
    add('-V', '--version', action='version', version=__version__)
    args = parser.parse_args()

    increase_logging_verbosity(args.verbose - args.quiet)

    m3u8_url = args.m3u8_url
    output = args.output

    if output is None:
        stem = pathlib.Path(urllib.parse.urlsplit(m3u8_url).path).stem
        if not stem or stem.startswith('.'):
            logger.critical(f'cannot auto-determine an output file from {m3u8_url}')
            return 1
        output = pathlib.Path(f'{stem}.mp4')
        logger.info(f'output not specified; using {output}')

    if not output.parent.exists():
        logger.critical(f'{output.parent} does not exist')
        return 1

    if not output.suffix:
        logger.critical(f'output must have a suffix, e.g., .mp4')
        return 1

    if output.exists() and not args.force:
        logger.critical(f'{output} already exists; specify --force to overwrite it')
        return 1

    if not output.exists():
        # Make sure output (especially if it's auto-deduced from URL, which
        # might contain reserved characters on Windows) is a valid path and is
        # writable.
        try:
            with open(output, 'wb'):
                pass
            output.unlink()
        except OSError:
            logger.critical(f'{output} is not a valid path or is not writable')
            return 1

    if args.jobs is not None and args.jobs <= 0:
        logger.critical('jobs must be positive')
        return 1

    if args.concat_method == '0':
        args.concat_method = 'concat_demuxer'
    elif args.concat_method == '1':
        args.concat_method = 'concat_protocol'

    remote_m3u8_url = m3u8_url
    working_directory = output.with_suffix('')
    if args.wipe and working_directory.exists():
        logger.info(f'wiping {working_directory}')
        try:
            if working_directory.is_file():
                working_directory.unlink()
            else:
                shutil.rmtree(working_directory)
        except OSError as e:
            logger.critical(f'failed to wipe {working_directory}: {excname(e)}: {e}')
            return 1
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
        merge.incremental_merge(local_m3u8_file, output,
                                concat_method=args.concat_method)
        if not args.keep:
            shutil.rmtree(working_directory)
    except RuntimeError as e:
        logger.critical(e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
