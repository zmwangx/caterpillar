import contextlib
import logging
import os
import pathlib
from typing import Iterable, Tuple


logger = logging.getLogger('caterpillar')
_fmt = logging.Formatter(fmt='[%(levelname)s] %(message)s')
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_sh)
logger.setLevel(logging.INFO)


def increase_logging_verbosity(num_levels):
    target_level = logger.level - num_levels * 10
    target_level = min(max(target_level, logging.DEBUG), logging.CRITICAL)
    logger.setLevel(target_level)


# Returns the qualified name of an exeception.
def excname(value):
    etype = type(value)
    if etype.__module__ == 'builtins':
        return etype.__name__
    else:
        return '%s.%s' % (etype.__module__, etype.__name__)


# Resolve a pathlib.Path that may not exist yet. Assumes that the parent
# of the path already exists.
#
# This is to workaround pathlib.Path.resolve() behavior on Windows: if
# the relative path does not already exist, the return value is not an
# absolute path.
def abspath(path: pathlib.Path) -> pathlib.Path:
    return path.parent.resolve().joinpath(path.name)


@contextlib.contextmanager
def chdir(directory):
    cwd = os.getcwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(cwd)


# A bare minimum M3U8 generator (HLSv3).
#
# segments is an iterable of tuples (url, duration).
#
# Note that the only required media playlist tag is
# EXT-X-TARGETDURATION, and the only required media segment tag is
# EXTINF. Additionally, we use 3 as EXT-X-VERSION for floating-point
# EXTINF duration values.[1]
#
# [1] https://tools.ietf.org/html/rfc8216#section-7
def generate_m3u8(target_duration: int, segments: Iterable[Tuple[str, float]]):
    lines = []
    lines.append('#EXTM3U')
    lines.append('#EXT-X-VERSION:3')
    lines.append(f'#EXT-X-TARGETDURATION:{target_duration}')
    for url, duration in segments:
        lines.append(f'#EXTINF:{duration},')
        lines.append(url)
    lines.append('#EXT-X-ENDLIST')
    lines.append('')
    return '\n'.join(lines)
