#!/usr/bin/env python3

import argparse
import datetime
import os
import pathlib
import shutil
import sys
import time
import urllib.parse
from typing import Any, List, Optional

import peewee

from . import download, merge, persistence
from .utils import (
    UESR_CONFIG_DIR,
    USER_CONFIG_DISABLED,
    abspath,
    logger,
    increase_logging_verbosity,
    should_log_warning,
)
from .version import __version__


USER_CONFIG_FILE = pathlib.Path(UESR_CONFIG_DIR).joinpath("caterpillar.conf")


ADDITIONAL_HELP_TEXT = f"""
environment variables:
  CATERPILLAR_USER_CONFIG_DIR
                        custom directory for caterpillar.conf
  CATERPILLAR_USER_DATA_DIR
                        custom directory for certain data cached by
                        caterpillar
  CATERPILLAR_NO_USER_CONFIG
                        when set to a non-empty value, do not load
                        options from user config file
  CATERPILLAR_NO_CACHE  when set to a non-empty value, do not read or
                        write caterpillar's cache

configuration file:
  {USER_CONFIG_FILE}

"""


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parsing_with_config_defaults = False

    # config_defaults is a list of arguments parsed from user config
    # file; see load_user_config().
    def parse_args_with_user_config(
        self,
        args: List[str] = None,
        namespace: argparse.Namespace = None,
        config_defaults: List[str] = None,
    ) -> argparse.Namespace:
        if config_defaults is None:
            return super().parse_args(args, namespace=namespace)
        else:
            if args is None:
                args = sys.argv[1:]
            try:
                self.parsing_with_config_defaults = True
                return super().parse_args(config_defaults + args, namespace=namespace)
            finally:
                self.parsing_with_config_defaults = False

    def format_help(self) -> str:
        help_text = super().format_help()
        return help_text + ADDITIONAL_HELP_TEXT

    def error(self, message):
        self.print_usage(sys.stderr)
        msg = f"{self.prog}: error: {message}\n"
        if self.parsing_with_config_defaults:
            msg += (
                f'You may want to check your config file "{USER_CONFIG_FILE}" '
                f"for invalid arguments.\n"
            )
        self.exit(2, msg)


CONFIG_FILE_TEMPLATE = """\
# You may configure default options here so that you don't need to
# specify the same options on the command line every time.
#
# Each option, along with its argument (if any), should be on a separate
# line; unlike on the command line, you don't need to quote or escape
# whitespace or other special characters in an argument, e.g., a line
#
#     --workdir Temporary Directory
#
# is interpreted as two command line arguments "--workdir" and
# "Temporary Directory".
#
# Positional arguments are not allowed, i.e., option lines must begin
# with -.
#
# Blank lines and lines starting with a pound (#) are ignored.
#
# You can always override the default options here on the command line.
#
# Examples:
#
#     --jobs 32
#     --concat-method concat_protocol
"""


def load_user_config() -> List[str]:
    try:
        if USER_CONFIG_FILE.is_file():  # pylint: disable=no-member
            args = []
            with open(USER_CONFIG_FILE, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not line.startswith("-"):
                        logger.warning(
                            f'illegal line in config file "{USER_CONFIG_FILE}": {line}'
                        )
                        continue
                    args.extend(line.split(maxsplit=1))
            return args
        else:
            # Try to create the config file with template
            USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(USER_CONFIG_FILE, "w", encoding="utf-8") as fp:
                fp.write(CONFIG_FILE_TEMPLATE)
            return []
    except OSError:
        logger.exc_warning("error loading user config")
        return []
    except UnicodeDecodeError:
        logger.warning(
            f'cannot decode config file "{USER_CONFIG_FILE}" as utf-8; '
            "see https://git.io/caterpillar-encoding"
        )
        return []


# A return value of None means preparation of working directory failed.
@persistence.atomic
def prepare_working_directory(
    m3u8_url: str,
    output_file: pathlib.Path,
    *,
    workroot: pathlib.Path = None,
    user_specified_workdir: pathlib.Path = None,
    wipe: bool = False,
) -> Optional[pathlib.Path]:
    if user_specified_workdir:
        workdir = user_specified_workdir
        if workroot:
            workdir = map_path(workdir, workroot)
    else:
        workdir = output_file.with_suffix("")
        if workroot:
            workdir = map_path(workdir, workroot)
        try:
            cached_workdir = persistence.get_workdir(m3u8_url)
        except peewee.PeeweeException:
            logger.exc_error("exception when reading cache")
        if cached_workdir:
            if cached_workdir.is_dir():
                if abspath(workdir) != abspath(cached_workdir):
                    logger.warning(
                        f'using "{cached_workdir}" as working directory '
                        f"for segments and other intermediate files; "
                        f"use --workdir option to specify a different "
                        f"working directory"
                    )
                    workdir = cached_workdir
            else:
                try:
                    persistence.drop(m3u8_url)
                except peewee.PeeweeException:
                    logger.exc_error("exception when updating cache")

    if wipe and workdir.exists():
        logger.info(f"wiping {workdir}")
        try:
            if workdir.is_file():
                workdir.unlink()
            else:
                shutil.rmtree(workdir)
        except OSError:
            logger.exc_error(f"failed to wipe {workdir}")
            return None

    try:
        # Only allow creating parent directories if using a nonempty workroot.
        workdir.mkdir(parents=bool(workroot), exist_ok=True)
    except OSError:
        logger.exc_error(f"failed to create {workdir}")
        return None

    try:
        persistence.insert(m3u8_url, workdir)
    except peewee.PeeweeException:
        logger.exc_error("exception when updating cache")

    return workdir


# Map path to an equivalent subpath of root, and create all missing
# ancestor directories. E.g., /home/caterpillar mapped under
# /var/run/caterpillar becomes /var/run/caterpillar/home/caterpillar.
#
# On Windows, drive letters are mapped to direct children of the
# workroot; e.g., C: mapped under C:\Users\caterpillar\AppData\Local\Temp
# becomes C:\Users\caterpillar\AppData\Local\Temp\C\. UNC shares
# \\host\share are mapped to host\share.
def map_path(path: pathlib.Path, root: pathlib.Path) -> pathlib.Path:
    path = path.resolve()
    drive = path.drive
    if not drive:
        subdir = ""
    elif drive.endswith(":") and not drive.startswith(os.sep):
        # Window drive letter, e.g., C:
        subdir = drive[:-1] + os.sep
        # UNC \\host\share
    elif drive.startswith(r"\\"):
        subdir = drive[2:] + os.sep
    else:
        raise ValueError(f"unrecognized drive {drive}; please report as bug")
    name = path.name
    ancestor = path.parent
    segments = []  # type: List[str]
    while ancestor.name:
        segments.insert(0, ancestor.name)
        ancestor = ancestor.parent
    subdir += os.sep.join(segments)
    mapped_dir = root.joinpath(subdir)
    mapped_dir.mkdir(parents=True, exist_ok=True)
    return mapped_dir.joinpath(name)


def rmdir_p(path: pathlib.Path, *, root: pathlib.Path = None) -> None:
    path = path.resolve()
    if root:
        root = root.resolve()
    while path.name and path != root:
        try:
            path.rmdir()
        except OSError:
            break
        path = path.parent


# Returns the backup path.
def move_to_backup(path: pathlib.Path) -> Optional[pathlib.Path]:
    directory = path.parent
    filename = path.name
    backup = directory / f"{filename}.bak"
    if backup.exists():
        dedup = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup = directory / f"{filename}.{dedup}.bak"
        if backup.exists():
            index = 1
            while backup.exists():
                backup = directory / f"{filename}.{dedup}.bak.{index}"
                index += 1
    logger.info(f'moving "{path}" to "{backup}"...')
    try:
        os.rename(path, backup)
        return backup
    except OSError:
        logger.error(f'failed to move "{path}" to "{backup}"')
        return None


def process_entry(
    m3u8_url: str,
    output: pathlib.Path,
    *,
    force: bool = False,
    exist_ok: bool = False,
    workdir: pathlib.Path = None,
    workroot: pathlib.Path = None,
    wipe: bool = False,
    keep: bool = False,
    jobs: int = None,
    concat_method: str = "concat_demuxer",
    retries: int = 0,
    progress: bool = True,
) -> int:
    if output is None:
        stem = pathlib.Path(urllib.parse.urlsplit(m3u8_url).path).stem
        if not stem or stem.startswith("."):
            logger.critical(f"cannot auto-determine an output file from {m3u8_url}")
            return 1
        output = pathlib.Path(f"{stem}.mp4")
        logger.info(f'output not specified; using "{output}"')

    if not output.parent.exists():
        logger.critical(f'"{output.parent}" does not exist')
        return 1

    if not output.suffix:
        logger.critical(f"output must have a suffix, e.g., .mp4")
        return 1

    if output.exists() and not force:
        if exist_ok:
            sys.stderr.write(f'"{output}" already exists\n')
            return 0
        else:
            logger.critical(
                f'"{output}" already exists; specify --force to overwrite it'
            )
            return 1

    backup = None
    if output.exists() and force:
        backup = move_to_backup(output)
        if backup is None:
            logger.critical(f'failed to backup "{output}"')
            return 1

    merge_dest = output
    if workroot:
        merge_dest = map_path(output, workroot)

    if merge_dest.exists() and not force:
        logger.critical(
            f'"{merge_dest}"" already exists; '
            "specify --force to overwrite it, or manually remove it and try again"
        )
        return 1

    # Make sure output (especially if it's auto-deduced from URL, which
    # might contain reserved characters on Windows) is a valid path and is
    # writable.
    try:
        with open(output, "wb"):
            pass
        output.unlink()
    except OSError:
        logger.critical(f'"{output}" is not a valid path or is not writable')
        return 1

    remote_m3u8_url = m3u8_url
    working_directory = prepare_working_directory(
        remote_m3u8_url,
        output,
        workroot=workroot,
        user_specified_workdir=workdir,
        wipe=wipe,
    )
    if not working_directory:
        logger.critical("failed to prepare working directory")
        return 1
    remote_m3u8_file = working_directory / "remote.m3u8"
    local_m3u8_file = working_directory / "local.m3u8"
    for ntry in range(max(retries, 0) + 1):
        try:
            if not download.download_m3u8_file(remote_m3u8_url, remote_m3u8_file):
                # Return without retries because we already retried a
                # couple of times in download_m3u8_file.
                logger.critical(f"failed to download {remote_m3u8_url}")
                return 1
            logger.info(f"downloaded {remote_m3u8_file}")
            if not download.download_m3u8_segments(
                remote_m3u8_url,
                remote_m3u8_file,
                local_m3u8_file,
                jobs=jobs,
                progress=progress,
            ):
                raise RuntimeError("failed to download some segments")
            merge.incremental_merge(
                local_m3u8_file, merge_dest, concat_method=concat_method
            )
            if output != merge_dest:
                try:
                    logger.info(f'moving "{merge_dest}" to "{output}"...')
                    shutil.move(merge_dest, output)
                except OSError:
                    # This is unlikely a quickly retriable issue, so we
                    # return an error immediately.
                    logger.critical(f'failed to move "{merge_dest}" to "{output}"')
                    return 1
                rmdir_p(merge_dest.parent, root=workroot)

            if backup is not None:
                try:
                    logger.info(f'removing backup "{backup}"...')
                    os.unlink(backup)
                except OSError:
                    logger.warning(f'failed to remove backup "{backup}"')

            try:
                atime = time.time()
                mtime = os.stat(remote_m3u8_file).st_mtime
                logger.debug(f"setting mtime on {output} to {mtime}")
                os.utime(output, times=(atime, mtime))
            except OSError:
                logger.warning(f"failed to set mtime on {output}")

            if not keep:
                try:
                    persistence.drop(remote_m3u8_url)
                except peewee.PeeweeException:
                    logger.exc_error("exception when updating cache")
                shutil.rmtree(working_directory)
                if workroot:
                    rmdir_p(working_directory.parent, root=workroot)
            break
        except RuntimeError as e:
            if ntry == retries:
                logger.critical(str(e))
                return 1
            else:
                logger.error(str(e))
                logger.warning(f"retrying ({ntry + 1}/{retries}) in 5 seconds...")
                time.sleep(5)
    return 0


def process_batch(
    manifest: pathlib.Path,
    remove_manifest_on_success: bool = False,
    debug: bool = False,
    **processing_kwargs: Any,
) -> int:
    target_dir = manifest.parent
    try:
        entries = []
        with manifest.open(encoding="utf-8") as fp:
            manifest_content = fp.read()
    except OSError:
        logger.critical("cannot open batch mode manifest", exc_info=debug)
        if debug:
            raise
        return 1
    except UnicodeDecodeError:
        logger.critical(
            "cannot decode batch mode manifest as utf-8; "
            "see https://git.io/caterpillar-encoding",
            exc_info=debug,
        )
        if debug:
            raise
        return 1

    for line in manifest_content.splitlines():
        # Strip BOM to accommodate Notepad users.
        line = line.strip().lstrip("\uFEFF")
        if line.startswith("#"):
            continue
        try:
            m3u8_url, filename = line.split("\t")
            output = target_dir.joinpath(filename)
            entries.append((m3u8_url, output))
        except Exception:
            logger.critical(
                "malformed line in batch mode manifest: %s", line, exc_info=debug
            )
            if debug:
                raise
            return 1

    retvals = []
    count = len(entries)
    for i, (m3u8_url, output) in enumerate(entries):
        sys.stderr.write(
            f'[{i + 1}/{count}] Downloading {m3u8_url} into "{output}"...\n'
        )
        retvals.append(process_entry(m3u8_url, output, **processing_kwargs))
        sys.stderr.write("\n")
    retval = int(any(retvals))
    if retval == 0 and remove_manifest_on_success:
        try:
            manifest.unlink()
        except OSError:
            logger.error("cannot remove batch mode manifest")
            if debug:
                raise
            return 1
    return retval


def main() -> int:
    user_config_options = [] if USER_CONFIG_DISABLED else load_user_config()

    parser = ArgumentParser()
    add = parser.add_argument
    add("m3u8_url", help="the VOD URL, or the batch mode manifest file")
    add(
        "output",
        nargs="?",
        type=pathlib.Path,
        default=None,
        help="""path to the final output file (default is a .ts file in the
        current directory with the basename of the VOD URL)""",
    )
    add(
        "-b",
        "--batch",
        action="store_true",
        help='run in batch mode (see the "Batch Mode" section in docs)',
    )
    add(
        "-e",
        "--exist-ok",
        action="store_true",
        help="skip existing targets (only works in batch mode)",
    )
    add(
        "-f",
        "--force",
        action="store_true",
        help="overwrite the output file if it already exists",
    )
    add(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="""maximum number of concurrent downloads (default is twice
        the number of CPU cores, including virtual cores)""",
    )
    add(
        "-k",
        "--keep",
        action="store_true",
        help="keep intermediate files even after a successful merge",
    )
    add(
        "-m",
        "--concat-method",
        choices=["concat_demuxer", "concat_protocol", "0", "1"],
        default="concat_demuxer",
        help="""method for concatenating intermediate files (default is
        'concat_demuxer'); see
        https://github.com/zmwangx/caterpillar/#notes-and-limitations
        for details""",
    )
    add(
        "-r",
        "--retries",
        type=int,
        default=2,
        help="""number of times to retry when a possibly recoverable
        error (e.g. download issue) occurs; default is 2, and 0 turns
        off retries""",
    )
    add(
        "--remove-manifest-on-success",
        action="store_true",
        help="""remove manifest file if all downloads are successful
        (only works in batch mode)""",
    )
    add(
        "--workdir",
        type=pathlib.Path,
        help="""working directory to store downloaded segments and other
        intermediate files (default is automatically determined based on
        URL and output file)""",
    )
    add(
        "--workroot",
        help="""if nonempty, this path is used as the root directory for
        all processing, under which both the working directory and final
        destination are mapped; after merging is done, the artifact is
        eventually moved to the destination (use cases: destination on
        a slow HDD with workroot on a fast SSD; destination on a
        networked drive with workroot on a local drive)""",
    )
    add(
        "--wipe",
        action="store_true",
        help="wipe all downloaded files (if any) and start over",
    )
    add(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase logging verbosity (can be specified multiple times)",
    )
    add(
        "--progress",
        action="store_true",
        help="show download progress bar regardless of verbosity level",
    )
    add(
        "--no-progress",
        action="store_true",
        help="suppress download progress bar regardless of verbosity level",
    )
    add(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="decrease logging verbosity (can be specified multiple times)",
    )
    add(
        "--debug",
        action="store_true",
        help="output debugging information (also implies highest verbosity)",
    )
    add("-V", "--version", action="version", version=__version__)

    # First make sure arguments on the command line are valid.
    args = parser.parse_args()

    if not USER_CONFIG_DISABLED:
        # Prepend defaults from user config and parse again. If parsing
        # fails this time, the error must be in the config file.
        args = parser.parse_args_with_user_config(config_defaults=user_config_options)

    increase_logging_verbosity(args.verbose - args.quiet)
    if args.debug:
        increase_logging_verbosity(5)

    if args.batch:
        if args.output:
            logger.critical("output file not allowed in bach mode")
            return 1
        if args.workdir:
            logger.critical("workdir not allowed in batch mode")
            return 1

    if args.workroot:
        args.workroot = pathlib.Path(args.workroot)
    else:
        args.workroot = None
    if args.workroot and not args.workroot.is_dir():
        logger.critical(f"{args.workroot} does not exist or is not a directory")

    if not args.workroot and args.workdir and not args.workdir.parent.exists():
        logger.critical(f"{args.workdir.parent} does not exist")
        return 1

    if args.jobs is not None and args.jobs <= 0:
        logger.critical("jobs must be positive")
        return 1

    if args.concat_method == "0":
        args.concat_method = "concat_demuxer"
    elif args.concat_method == "1":
        args.concat_method = "concat_protocol"

    if args.progress:
        progress = True
    elif args.no_progress:
        progress = False
    else:
        progress = should_log_warning()

    kwargs = dict(
        force=args.force,
        exist_ok=args.batch and args.exist_ok,
        workdir=args.workdir,
        workroot=args.workroot,
        wipe=args.wipe,
        keep=args.keep,
        jobs=args.jobs,
        concat_method=args.concat_method,
        retries=args.retries,
        progress=progress,
    )

    if shutil.which("ffmpeg") is None:
        logger.critical("ffmpeg not found")
        return 1

    try:
        if not args.batch:
            return process_entry(args.m3u8_url, args.output, **kwargs)
        else:
            manifest = pathlib.Path(args.m3u8_url).resolve()
            return process_batch(
                manifest,
                remove_manifest_on_success=args.remove_manifest_on_success,
                debug=args.debug,
                **kwargs,
            )
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
