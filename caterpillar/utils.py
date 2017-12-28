import contextlib
import logging
import os
import pathlib
import shutil
from typing import Iterable, Tuple


logger = logging.getLogger('caterpillar')
_fmt = logging.Formatter(fmt='[%(levelname)s] %(message)s')
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
logger.addHandler(_sh)
logger.setLevel(logging.WARNING)


def increase_logging_verbosity(num_levels):
    target_level = logger.level - num_levels * 10
    target_level = min(max(target_level, logging.DEBUG), logging.CRITICAL)
    logger.setLevel(target_level)


def should_log_error():
    return logger.isEnabledFor(logging.ERROR)


def should_log_warning():
    return logger.isEnabledFor(logging.WARNING)


def should_log_info():
    return logger.isEnabledFor(logging.INFO)


def should_log_debug():
    return logger.isEnabledFor(logging.DEBUG)


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


# Monkey patch shutil.get_terminal_size to fix full-width progress bar
# overflow problem on Windows consoles.
def monkeypatch_get_terminal_size():
    # Only monkey patch on NT, and only monkey patch once.
    if os.name != 'nt' or hasattr(shutil, 'original_get_terminal_size'):
        return
    shutil.original_get_terminal_size = shutil.get_terminal_size

    def replacement(fallback=None):
        columns, lines = shutil.original_get_terminal_size(fallback)
        # One fewer column so that full-width progress bar doesn't flow
        # onto the next line.
        return os.terminal_size((columns - 1, lines))

    shutil.get_terminal_size = replacement


# A stub class with support for random attribute access. All attributes
# not previously set are regarded as a stub method that takes any
# positional and keyword arguments and returns None.
class Stub(object):

    def __getattr__(self, name):
        def stub(*_, **__):
            return

        return stub

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


# A context manager factory that yields a Stub object and does no more.
@contextlib.contextmanager
def stub_context_manager(*_, **__):
    yield Stub()


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
