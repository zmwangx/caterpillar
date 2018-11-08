import email.utils
import multiprocessing
import os
import pathlib
import signal
import time
import urllib.parse
from typing import Optional, Tuple

import click
import m3u8
import requests

from .utils import (
    generate_m3u8,
    logger,
    monkeypatch_get_terminal_size,
    stub_context_manager,
)


CHUNK_SIZE = 65536  # Download chunk size (64K)
REQUESTS_TIMEOUT = 5  # Both connect timeout and read timeout
MAX_RETRY_INTERVAL = 30  # Upper bound on exponential backoff

# For proper progress bar rendering on Windows consoles.
monkeypatch_get_terminal_size()


# Get mtime from an HTTP response's Last-Modified header, or Date
# header.
#
# Note that using the Date header for mtime is non-standard. Neither
# wget or aria2 considers the Date header.
def get_mtime(r: requests.Response) -> Optional[int]:
    modified = r.headers.get("Last-Modified") or r.headers.get("Date")
    if not modified:
        return None
    try:
        return int(email.utils.parsedate_to_datetime(modified).timestamp())
    except TypeError:
        return None


# Returns a bool indicating success (True) or failure (False).
#
# If server_timestamp is True, set mtime of the downloaded file
# according to timestamp reported by server.
def resumable_download(
    url: str, file: pathlib.Path, server_timestamp: bool = False
) -> bool:
    headers = dict()
    existing_bytes = file.stat().st_size if file.is_file() else 0
    if existing_bytes:
        headers["Range"] = f"bytes={existing_bytes}-"
    try:
        logger.debug(f"GET {url}")
        r = requests.get(url, headers=headers, stream=True, timeout=REQUESTS_TIMEOUT)
        if r.status_code not in {200, 206}:
            logger.error(f"GET {url}: HTTP {r.status_code}")
            return False
        with open(file, "ab") as fp:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fp.write(chunk)
        if server_timestamp:
            mtime = get_mtime(r)
            if mtime is not None:
                atime = time.time()
                try:
                    logger.debug(f"setting mtime on {file} to {mtime}")
                    os.utime(file, times=(atime, mtime))
                except OSError:
                    logger.warning(f"GET {url}: failed to set mtime on {file}")
        return True
    except Exception:
        logger.exc_warning(f"GET {url}")
        return False


# Returns a bool indicating success (True) or failure (False).
#
# If server_timestamp is True, set mtime of the downloaded file
# according to timestamp reported by server.
def resumable_download_with_retries(
    url: str, file: pathlib.Path, max_retries: int = 2, server_timestamp: bool = False
) -> bool:
    incomplete_file = file.with_suffix(file.suffix + ".incomplete")

    # If the file, without the .incomplete suffix, is already present,
    # assume it has been downloaded.
    if file.exists():
        return True

    retries = 0
    while True:
        if resumable_download(url, incomplete_file, server_timestamp=server_timestamp):
            os.replace(incomplete_file, file)
            return True

        if retries >= max_retries:
            logger.error(f"GET {url}: failed after {max_retries} retries")
            return False

        retries += 1
        wait_time = min(2 ** retries, MAX_RETRY_INTERVAL)
        logger.warning(f"GET {url}: retrying after {wait_time} seconds...")
        time.sleep(wait_time)


# Returns a bool indicating success (True) or failure (False).
def download_m3u8_file(m3u8_url: str, file: pathlib.Path) -> bool:
    logger.info(f"downloading {m3u8_url} to {file} ...")
    return resumable_download_with_retries(m3u8_url, file, server_timestamp=True)


# Returns a bool indicating success (True) or failure (False).
def download_segment(
    url: str, index: int, directory: pathlib.Path, max_retries: int = 2
) -> bool:
    return resumable_download_with_retries(
        url, directory / f"{index}.ts", max_retries=max_retries
    )


# download_segment wrapper that takes all arguments as a single tuple
# (with one additional argument: the logging level, so that it can be
# set correctly for worker processes -- there's no fork on Windows, so
# the worker processes do not actually inherit logger level), so that we
# can use it with multiprocessing.pool.Pool.map and company. It also
# gracefully consumes KeyboardInterrupt.
def _download_segment_mappable(args: Tuple[str, int, pathlib.Path, int]) -> bool:
    try:
        url, index, directory, logging_level = args
        logger.setLevel(logging_level)
        return download_segment(url, index, directory)
    except KeyboardInterrupt:
        url, *_ = args
        logger.debug(f"download of {url} has been interrupted")
        return False


def _raise_keyboard_interrupt(signum, _):
    pid = os.getpid()
    logger.debug(f"pid {pid} received signal {signum}; transforming into SIGINT")
    raise KeyboardInterrupt


# Download all segments in remote_m3u8_file (downloaded from
# remote_m3u8_url), and generates a local playlist in local_m3u8_file
# with local segment filenames (0.ts, 1.ts, 2.ts, etc.).
#
# jobs indicates the maximum number of parallel downloads. Default is
# twice os.cpu_count().
#
# Returns a bool indicating success (True) or failure (False). Note that
# an empty playlist (invalid) automatically results in a failure.
def download_m3u8_segments(
    remote_m3u8_url: str,
    remote_m3u8_file: pathlib.Path,
    local_m3u8_file: pathlib.Path,
    *,
    jobs: int = None,
    progress: bool = None,
) -> bool:
    if jobs is None:
        jobs = (os.cpu_count() or 4) * 2

    try:
        remote_m3u8_obj = m3u8.load(str(remote_m3u8_file))
    except Exception:
        logger.exc_error(f"failed to parse {remote_m3u8_file}")
        return False

    target_duration = remote_m3u8_obj.target_duration
    local_segments = []
    download_args = []
    logging_level = logger.getEffectiveLevel()
    for index, segment in enumerate(remote_m3u8_obj.segments):
        url = urllib.parse.urljoin(remote_m3u8_url, segment.uri)
        download_args.append((url, index, local_m3u8_file.parent, logging_level))
        local_segments.append((f"{index}.ts", segment.duration))

    with open(local_m3u8_file, "w", encoding="utf-8") as fp:
        fp.write(generate_m3u8(target_duration, local_segments))
    logger.info(f"generated {local_m3u8_file}")

    total = len(download_args)
    if total == 0:
        logger.error(f"{remote_m3u8_file}: empty playlist")
        return False
    jobs = min(jobs, total)
    with multiprocessing.Pool(jobs) as pool:
        # For the duration of the worker pool, map SIGTERM to SIGINT on
        # the main process. We only do this after the fork, and restore
        # the original SIGTERM handler (usually SIG_DFL) at the end of
        # the pool, because using _raise_keyboard_interrupt as the
        # SIGTERM handler on workers could somehow lead to dead locks.
        old_sigterm_handler = signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
        try:
            num_success = 0
            num_failure = 0
            logger.info(f"downloading {total} segments with {jobs} workers...")
            progress_bar_generator = (
                click.progressbar if progress else stub_context_manager
            )
            progress_bar_props = dict(
                width=0,  # Full width
                bar_template="[%(bar)s] %(info)s",
                show_pos=True,
                length=total,
            )
            with progress_bar_generator(**progress_bar_props) as bar:  # type: ignore
                for success in pool.imap_unordered(
                    _download_segment_mappable, download_args
                ):
                    if success:
                        num_success += 1
                    else:
                        num_failure += 1
                    logger.debug(f"progress: {num_success}/{num_failure}/{total}")
                    bar.update(1)

            if num_failure > 0:
                logger.error(f"failed to download {num_failure} segments")
                return False
            else:
                logger.info(f"finished downloading all {total} segments")
                return True
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
            logger.critical("interrupted")
            # Bubble KeyboardInterrupt to stop retries.
            raise KeyboardInterrupt
        finally:
            signal.signal(signal.SIGTERM, old_sigterm_handler)
