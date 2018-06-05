import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Optional, Tuple

import m3u8

from .utils import (
    abspath,
    chdir,
    generate_m3u8,
    logger,
    should_log_info,
)


# If ignore_errors is True, blast through non-monotonous DTS errors
# without looking back. We use this after on a splitted playlist deemed
# all good, since for some mysterious reason, probably due to artifacts
# in some hopelessly bad segments, it seems possible that a
# non-monotonous DTS error would manifest only on the second pass, after
# the playlist is splitted. An example:
#
#   http://live.us.sinaimg.cn/000XDYqUjx07gRaRHSCz070d010002TZ0k01.m3u8
#
# On the first pass of merging 4.m3u8, we only get the non-monotonous
# DTS error at 13.ts, but after splitting, on the second pass, we also
# get a non-monotonous error from 12.ts, following a "missing picture in
# access unit with size 6" error.
#
# Returns None if the merge succeeds, or the basename of the first bad
# segment if non-monotonous DTS is detected.
def attempt_merge(m3u8_file: pathlib.Path, output: pathlib.Path,
                  ignore_errors: bool = False) -> Optional[str]:
    logger.info(f'attempting to merge {m3u8_file} into {output}')

    m3u8_obj = m3u8.load(m3u8_file.as_posix())
    if len(m3u8_obj.segments) == 1:
        # Only one segment, cannot further subdivide, so ignore whatever
        # problems there may be.
        logger.info(f'only one segment in playlist; ignoring errors and warnings')
        ignore_errors = True

    regular_pattern = re.compile(r"Opening '(?P<path>.*\.ts)' for reading")
    error_pattern = re.compile(
        r'(Non-monotonous DTS in output stream|out of range for mov/mp4 format)')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'info',
               '-f', 'hls', '-i', m3u8_file.as_posix(), '-c', 'copy', '-y', output.as_posix()]
    p = subprocess.Popen(command, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE,
                         universal_newlines=True, bufsize=1,
                         encoding='utf-8', errors='backslashreplace')
    last_read_segment = None
    for line in p.stderr:
        m = regular_pattern.search(line)
        # Suppress the line if logging level is below INFO and it's just
        # a boring "Opening '...' for reading" message.
        if not m or should_log_info():
            sys.stderr.write(line)
            sys.stderr.flush()
        if m:
            last_read_segment = os.path.basename(m['path'])
            continue
        if ignore_errors:
            continue
        if error_pattern.search(line):
            assert last_read_segment
            logger.warning(f'DTS jump detected in {last_read_segment}')
            if last_read_segment == m3u8_obj.segments[0].uri:
                logger.warning(f'{last_read_segment} is the first segment in playlist; '
                               f'splitting at the next segment')
                split_point = m3u8_obj.segments[1].uri
            else:
                split_point = last_read_segment

            p.stderr.close()
            p.terminate()
            # Deal with Windows process and file ownership idiosyncrasies.
            # On *ix this is immediate.
            while True:
                try:
                    output.unlink()
                except PermissionError:
                    # On Windows, the ffmpeg subprocess is not yet
                    # cleaned up and is still clinging to this file;
                    # wait until it is released, or the next subprocess
                    # may not even be able to successfully overwrite
                    # this file.
                    time.sleep(0.1)
                except FileNotFoundError:
                    break
                else:
                    break

            return split_point
    returncode = p.wait()
    if returncode != 0:
        logger.error(f'ffmpeg failed with exit status {returncode}')
        raise RuntimeError('unknown error occurred during merging')
    else:
        return None


# Split the source m3u8 file into two destination m3u8 files, at
# split_point, which is the URL of a segment. split_point belongs to the
# second file after splitting.
#
# It's safe to overwrite the source file with one of the destinations.
def split_m3u8(source: pathlib.Path, destinations: Tuple[pathlib.Path, pathlib.Path],
               split_point: str) -> None:
    logger.info(f'splitting {source} at {split_point}')
    m3u8_obj = m3u8.load(source.as_posix())
    target_duration = m3u8_obj.target_duration
    part1_segments = []
    part2_segments = []
    reached_split_point = False
    for segment in m3u8_obj.segments:
        if segment.uri == split_point:
            reached_split_point = True
        tup = (segment.uri, segment.duration)
        if reached_split_point:
            part2_segments.append(tup)
        else:
            part1_segments.append(tup)
    dest1, dest2 = destinations
    with open(dest1, 'w') as fp:
        fp.write(generate_m3u8(target_duration, part1_segments))
    logger.info(f'wrote {dest1}')
    with open(dest2, 'w') as fp:
        fp.write(generate_m3u8(target_duration, part2_segments))
    logger.info(f'wrote {dest2}')


# concat_method is either 'concat_demuxer'[1] or 'concat_protocol'[2].
# Sometimes one works better than other, but there's no clear winner in all
# cases.
#
# m3u8_file should not be named '1.m3u8'; in fact, avoid naming it
# '<number>.m3u8', or it may be overwritten in the process.
#
# [1] https://ffmpeg.org/ffmpeg-all.html#concat-1
# [2] https://ffmpeg.org/ffmpeg-all.html#concat-2
def incremental_merge(m3u8_file: pathlib.Path, output: pathlib.Path,
                      concat_method: str = 'concat_demuxer'):
    # Resolve output so that we don't write to a different relative path
    # later when we run FFmpeg from a different pwd.
    output = abspath(output)
    directory = m3u8_file.parent
    playlist_index = 1
    playlist = directory / f'{playlist_index}.m3u8'
    shutil.copyfile(m3u8_file, playlist)

    intermediate_dir = directory / 'intermediate'
    intermediate_dir.mkdir(exist_ok=True)

    while True:
        merge_dest = intermediate_dir / f'{playlist_index}.mp4'
        split_point = attempt_merge(playlist, merge_dest)
        if not split_point:
            break
        playlist_index += 1
        next_playlist = directory / f'{playlist_index}.m3u8'
        split_m3u8(playlist, (playlist, next_playlist), split_point)
        attempt_merge(playlist, merge_dest, ignore_errors=True)
        playlist = next_playlist

    with chdir(intermediate_dir):
        if concat_method == 'concat_demuxer':
            with open('concat.txt', 'w') as fp:
                for index in range(1, playlist_index + 1):
                    print(f'file {index}.mp4', file=fp)

            command = ['ffmpeg', '-hide_banner', '-loglevel', 'info',
                       '-f', 'concat', '-i', 'concat.txt',
                       '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-movflags', 'faststart',
                       '-y', output.as_posix()]
        elif concat_method == 'concat_protocol':
            ffmpeg_input = 'concat:' + '|'.join(f'{i}.mp4' for i in range(1, playlist_index + 1))
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'info', '-i', ffmpeg_input,
                       '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-movflags', 'faststart',
                       '-y', output.as_posix()]
        else:
            raise NotImplementedError(f"unrecognized concat method '{concat_method}'")

        try:
            logger.info('merging intermediate products...')
            subprocess.run(command, stdin=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f'ffmpeg failed with exit status {e.returncode}')
            raise RuntimeError('unknown error occurred during merging')
        else:
            logger.info(f'merged into {output}')
