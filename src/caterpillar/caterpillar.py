#!/usr/bin/env python3

import argparse
import pathlib
import shutil
import sys
import urllib.parse

import peewee

from . import download, merge, persistence
from .utils import abspath, excname, logger, increase_logging_verbosity
from .version import __version__


# A return value of None means preparation of working directory failed.
@persistence.atomic
def prepare_working_directory(m3u8_url: str,
                              output_file: pathlib.Path,
                              user_specified_workdir: pathlib.Path = None,
                              wipe: bool = False) -> pathlib.Path:
    if user_specified_workdir:
        workdir = user_specified_workdir
    else:
        workdir = output_file.with_suffix('')
        try:
            cached_workdir = persistence.get_workdir(m3u8_url)
        except peewee.PeeweeException as e:
            logger.error(f'exception when reading cache: {excname(e)}: {e}')
        if cached_workdir:
            if cached_workdir.is_dir():
                if abspath(workdir) != abspath(cached_workdir):
                    logger.warning(f'using "{cached_workdir}" as working directory '
                                   f'for segments and other intermediate files; '
                                   f'use --workdir option to specify a different '
                                   f'working directory')
                    workdir = cached_workdir
            else:
                try:
                    persistence.drop(m3u8_url)
                except peewee.PeeweeException as e:
                    logger.error(f'exception when updating cache: {excname(e)}: {e}')

    if wipe and workdir.exists():
        logger.info(f'wiping {workdir}')
        try:
            if workdir.is_file():
                workdir.unlink()
            else:
                shutil.rmtree(workdir)
        except OSError as e:
            logger.error(f'failed to wipe {workdir}: {excname(e)}: {e}')
            return None

    try:
        workdir.mkdir(exist_ok=True)
    except OSError as e:
        logger.error(f'failed to create {workdir}: {excname(e)}: {e}')
        return None

    try:
        persistence.insert(m3u8_url, workdir)
    except peewee.PeeweeException as e:
        logger.error(f'exception when updating cache: {excname(e)}: {e}')

    return workdir


def main() -> int:
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
    add('--workdir', type=pathlib.Path,
        help='''working directory to store downloaded segments and other
        intermediate files (default is automatically determined based on
        URL and output file)''')
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

    if args.workdir and not args.workdir.parent.exists():
        logger.critical(f'{args.workdir.parent} does not exist')
        return 1

    if args.jobs is not None and args.jobs <= 0:
        logger.critical('jobs must be positive')
        return 1

    if args.concat_method == '0':
        args.concat_method = 'concat_demuxer'
    elif args.concat_method == '1':
        args.concat_method = 'concat_protocol'

    remote_m3u8_url = m3u8_url
    working_directory = prepare_working_directory(remote_m3u8_url,
                                                  output,
                                                  user_specified_workdir=args.workdir,
                                                  wipe=args.wipe)
    if not working_directory:
        logger.critical('failed to prepare working directory')
        return 1
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
            try:
                persistence.drop(remote_m3u8_url)
            except peewee.PeeweeException as e:
                logger.error(f'exception when updating cache: {excname(e)}: {e}')
            shutil.rmtree(working_directory)
    except RuntimeError as e:
        logger.critical(e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
