<h1 align="center">Caterpillar</h1>

<p align="center">
  <a href="https://pypi.python.org/pypi/caterpillar-hls"><img src="https://img.shields.io/pypi/v/caterpillar-hls.svg?maxAge=3600" alt="pypi"></a>
  <img src="https://img.shields.io/badge/python-3.6,%203.7-blue.svg?maxAge=86400" alt="python: 3.6, 3.7">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg?maxAge=86400" alt="license: MIT">
  <a href="https://travis-ci.org/zmwangx/caterpillar"><img src="https://travis-ci.org/zmwangx/caterpillar.svg?branch=master" alt="travis"></a>
</p>

<p align="center"><img src="https://user-images.githubusercontent.com/4149852/34367011-a9b11be8-ea72-11e7-8a96-ce34dae1eb0f.jpg" alt="Caterpillar" width="400" height="242"></p>

`caterpillar` is a hardened HLS merger. It takes an HTTP Live Streaming VOD URL (typically an .m3u8 URL), downloads the video segments, and attempts to merge them into a single, coherent file. It is specially designed to combat timestamp discontinuities (symptom: a naive FFmpeg run spews tons of "Non-monotonous DTS in output stream" warning messages and ends up with a useless file with completely broken timestamps).

`caterpillar` supports [up to version 3](https://tools.ietf.org/html/rfc8216#section-7) of the HTTP Live Streaming protocol (VOD only; non-VOD playlists are treated as VOD, and may result in unexpected consequences).

## Contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Dependencies](#dependencies)
- [Installation](#installation)
  - [For end users](#for-end-users)
  - [For developers and beta testers](#for-developers-and-beta-testers)
- [Usage](#usage)
- [Batch mode](#batch-mode)
- [Configuration](#configuration)
- [Notes and limitations](#notes-and-limitations)
- [Etymology](#etymology)
- [Copyright](#copyright)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Dependencies

A recent version of [FFmpeg](https://ffmpeg.org/download.html). FFmpeg 3.3.4 is known to work with caterpillar; FFmpeg 3.2.4 is known to NOT work.

## Installation

Python 3.6 or later is required.

*If in doubt, check out the detailed "[Installation Guide for Novices](https://github.com/zmwangx/caterpillar/wiki/Installation-Guide-for-Novices)".*

### For end users

To install,

```
pip install caterpillar-hls
```

To upgrade to the latest version,

```
pip install -U caterpillar-hls
```

### For developers and beta testers

To install from the master branch,

```
git clone https://github.com/zmwangx/caterpillar.git
cd caterpillar
python setup.py develop
caterpillar -h
```

To update to the latest master,

```
cd /path/to/caterpillar
git pull origin master
```

## Usage

```console
$ caterpillar -h
usage: caterpillar [-h] [-b] [-f] [-j JOBS] [-k]
                   [-m {concat_demuxer,concat_protocol,0,1}]
                   [--workdir WORKDIR] [--wipe] [-v] [-q] [-V]
                   m3u8_url [output]

positional arguments:
  m3u8_url              the VOD URL, or the batch mode manifest file
  output                path to the final output file (default is a .ts file
                        in the current directory with the basename of the VOD
                        URL)

optional arguments:
  -h, --help            show this help message and exit
  -b, --batch           run in batch mode (see the "Batch Mode" section in
                        docs)
  -f, --force           overwrite the output file if it already exists
  -j JOBS, --jobs JOBS  maximum number of concurrent downloads (default is
                        twice the number of CPU cores, including virtual
                        cores)
  -k, --keep            keep intermediate files even after a successful merge
  -m {concat_demuxer,concat_protocol,0,1}, --concat-method {concat_demuxer,concat_protocol,0,1}
                        method for concatenating intermediate files (default
                        is 'concat_demuxer'); see
                        https://github.com/zmwangx/caterpillar/#notes for
                        details
  --workdir WORKDIR     working directory to store downloaded segments and
                        other intermediate files (default is automatically
                        determined based on URL and output file)
  --wipe                wipe all downloaded files (if any) and start over
  -v, --verbose         increase logging verbosity (can be specified multiple
                        times)
  -q, --quiet           decrease logging verbosity (can be specified multiple
                        times)
  -V, --version         show program's version number and exit

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
  <an operating system and user-dependent path>

```

See the [wiki page](https://github.com/zmwangx/caterpillar/wiki/Usage-Examples) for usage examples.

## Batch mode

In normal mode, `caterpillar` deals with only one stream. There is also a batch mode for downloading multiple streams at once. In this mode, you specify a manifest file on the command line in the place of the VOD URL, where the manifest file contains a VOD URL and a filename (or path) seperated by a tab on each line, e.g., `caterpillar manifest.txt`, where `manifest.txt` contains

```
https://example.com/hls/1.m3u8	1.mp4
https://example.com/hls/2.m3u8	2.mp4
https://example.com/hls/3.m3u8	3.mp4
```

The filenames (or paths) are relative to the parent directory of the manifest file. The tab character is not allowed in the filenames (or paths).

Most options for normal mode are also allowed in the batch mode, as are options set in the configuration file.

## Configuration

To save some retyping, `caterpillar` supports the configuration of default options in an operating system and user-dependent configuration file. The path is usually `~/Library/Application Support/caterpillar/caterpillar.conf` on macOS, `%AppData%\org.zhimingwang\caterpillar\caterpillar.conf` on Windows, and `~/.config/caterpillar/caterpillar.conf` on Linux. Run `caterpillar -h` to view the actual path.

The syntax of the configuration file is documented in the template (automatically created for you if possible), duplicated below:

```
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
```

## Notes and limitations

- [`EXT-X-STREAM-INF` (and `EXT-X-I-FRAME-STREAM-INF` by extension)](https://tools.ietf.org/html/rfc8216#section-4.3.4.2), despite being part of protocol version 1, is not supported due to complexity and inherent conflict with caterpillar's working model (only one rendition is allowed). One has to preprocess a stream with `EXT-X-STREAM-INF` and pick out the variant stream to be used with caterpillar.

  Efforts could be made to extract the variant streams and show them to the user, and it is even feasible to proceed with the download if only one variant stream is present. Contribution is welcome for this feature.

- **A note on `-m, --concat-method`**: The final step of `caterpillar` is concatenating one or more parts (generated from splitted playlists with FFmpeg's `hls` demuxer) into a single output file. In this step we provide two methods of choice: the [concat demuxer](https://ffmpeg.org/ffmpeg-all.html#concat-1) and the [concat protocol](https://ffmpeg.org/ffmpeg-all.html#concat-1) (the former is the default). To pick the non-default `concat_protocol`, specify `--concat-method concat_protocol` on the command line, or as a shortcut, `-m 1` (`0` is an alias for `concat_demuxer`, and `1` is an alias for `concat_protocol`).

  Each of these two methods may work better in certain cases. For instance, for [this stream](http://ts.snh48.com/chaoqing/8001/20171201185235-playlist.m3u8?beginTime=20171201205500&endTime=20171201210500), the concat demuxer simply fails with loads of error messages like "Application provided duration: 7980637472 / timestamp: 7994129672 is out of range for mov/mp4 format", whereas the concat protocol works fine. However, for [this stream](http://live.us.sinaimg.cn/000XDYqUjx07gRaRHSCz070d010002TZ0k01.m3u8), the concat protocol dumps a bunch of worrisome warnings like "DTS out of order" or "Non-monotonous DTS in output stream", whereas the concat demuxer doesn't.

  *In short, if the default fails you (either doesn't work outright, or the generated video is bad in some way), try `-m 1`.*

## Etymology

The word "caterpillar" starts with `cat(1)`, and the body of a caterpillar is segmented.

## Copyright

Copyright © 2017 Zhiming Wang

This project is licensed under [the MIT license](https://opensource.org/licenses/MIT). See `COPYING` for details.

[The image of the caterpillar](https://en.wikipedia.org/wiki/File:Chenille_de_Grand_porte_queue_(macaon).jpg) by Didier Descouens is distributed under the [Creative Commons Attribution-Share Alike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/) license.
