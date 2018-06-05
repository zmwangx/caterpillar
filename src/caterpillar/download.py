import multiprocessing
import os
import pathlib
import signal
import time
import urllib.parse
from typing import Tuple

import click
import m3u8
import requests

from .utils import (
    generate_m3u8,
    logger,
    monkeypatch_get_terminal_size,
    should_log_warning,
    stub_context_manager,
)


CHUNK_SIZE = 65536  # Download chunk size (64K)
REQUESTS_TIMEOUT = 5  # Both connect timeout and read timeout
MAX_RETRY_INTERVAL = 30  # Upper bound on exponential backoff

# For proper progress bar rendering on Windows consoles.
monkeypatch_get_terminal_size()


# Returns a bool indicating success (True) or failure (False).
def resumable_download(url: str, file: pathlib.Path) -> bool:
    existing_bytes = file.stat().st_size if file.is_file() else 0
    try:
        logger.debug(f'GET {url}')
        r = requests.get(url, headers={'Range': f'bytes={existing_bytes}-'},
                         stream=True, timeout=REQUESTS_TIMEOUT)
        if r.status_code not in {200, 206}:
            logger.error(f'GET {url}: HTTP {r.status_code}')
            return False
        with open(file, 'ab') as fp:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fp.write(chunk)
        return True
    except Exception:
        logger.exc_warning(f'GET {url}')
        return False


# Returns a bool indicating success (True) or failure (False).
def resumable_download_with_retries(url: str, file: pathlib.Path,
                                    max_retries: int = 2) -> bool:
    incomplete_file = file.with_suffix(file.suffix + '.incomplete')

    # If the file, without the .incomplete suffix, is already present,
    # assume it has been downloaded.
    if file.exists():
        return True

    retries = 0
    while True:
        if resumable_download(url, incomplete_file):
            os.replace(incomplete_file, file)
            return True

        if retries >= max_retries:
            logger.error(f'GET {url}: failed after {max_retries} retries')
            return False

        retries += 1
        wait_time = min(2 ** retries, MAX_RETRY_INTERVAL)
        logger.warning(f'GET {url}: retrying after {wait_time} seconds...')
        time.sleep(wait_time)


# Returns a bool indicating success (True) or failure (False).
def download_m3u8_file(m3u8_url: str, file: pathlib.Path) -> bool:
    logger.info(f'downloading {m3u8_url} to {file} ...')
    return resumable_download_with_retries(m3u8_url, file)


# Returns a bool indicating success (True) or failure (False).
def download_segment(url: str, index: int, directory: pathlib.Path,
                     max_retries: int = 2) -> bool:
    return resumable_download_with_retries(url, directory / f'{index}.ts', max_retries=max_retries)


# download_segment wrapper that takes all arguments as a single tuple,
# so that we can use it with multiprocessing.pool.Pool.map and company.
def _download_segment_mappable(args: Tuple[str, int, pathlib.Path]) -> bool:
    return download_segment(*args)


def _init_worker():
    # Ignore SIGINT in worker processes to disable traceback from
    # each worker on keyboard interrupt.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


# Download all segments in remote_m3u8_file (downloaded from
# remote_m3u8_url), and generates a local playlist in local_m3u8_file
# with local segment filenames (0.ts, 1.ts, 2.ts, etc.).
#
# jobs indicates the maximum number of parallel downloads. Default is
# twice os.cpu_count().
#
# Returns a bool indicating success (True) or failure (False). Note that
# an empty playlist (invalid) automatically results in a failure.
def download_m3u8_segments(remote_m3u8_url: str,
                           remote_m3u8_file: pathlib.Path,
                           local_m3u8_file: pathlib.Path,
                           jobs: int = None) -> bool:
    if jobs is None:
        jobs = (os.cpu_count() or 4) * 2

    try:
        remote_m3u8_obj = m3u8.load(remote_m3u8_file.as_posix())
    except Exception:
        logger.exc_error(f'failed to parse {remote_m3u8_file}')
        return False

    target_duration = remote_m3u8_obj.target_duration
    local_segments = []
    download_args = []
    for index, segment in enumerate(remote_m3u8_obj.segments):
        url = urllib.parse.urljoin(remote_m3u8_url, segment.uri)
        download_args.append((url, index, local_m3u8_file.parent))
        local_segments.append((f'{index}.ts', segment.duration))

    with open(local_m3u8_file, 'w') as fp:
        fp.write(generate_m3u8(target_duration, local_segments))
    logger.info(f'generated {local_m3u8_file}')

    total = len(download_args)
    if total == 0:
        logger.error(f'{remote_m3u8_file}: empty playlist')
        return False
    jobs = min(jobs, total)
    with multiprocessing.Pool(jobs, _init_worker) as pool:
        num_success = 0
        num_failure = 0
        logger.info(f'downloading {total} segments with {jobs} workers...')
        progress_bar_generator = (click.progressbar if should_log_warning() else
                                  stub_context_manager)
        progress_bar_props = dict(
            width=0,  # Full width
            bar_template='[%(bar)s] %(info)s',
            show_pos=True,
            length=total,
        )
        with progress_bar_generator(**progress_bar_props) as bar:  # type: ignore
            for success in pool.imap_unordered(_download_segment_mappable, download_args):
                if success:
                    num_success += 1
                else:
                    num_failure += 1
                logger.debug(f'progress: {num_success}/{num_failure}/{total}')
                bar.update(1)

        if num_failure > 0:
            logger.error(f'failed to download {num_failure} segments')
            return False
        else:
            logger.info(f'finished downloading all {total} segments')
            return True
