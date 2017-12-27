<h1 align="center">Caterpillar</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.6-orange.svg?maxAge=86400" alt="python: 3.6">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg?maxAge=86400" alt="license: MIT">
</p>

<p align="center"><img src="https://user-images.githubusercontent.com/4149852/34367011-a9b11be8-ea72-11e7-8a96-ce34dae1eb0f.jpg" alt="Caterpillar" width="400" height="242"></p>

`caterpillar` is a hardened HLS merger. It takes an HTTP Live Streaming VOD URL (typically an .m3u8 URL), downloads the video segments, and attempts to merge them into a single, coherent file. It is specially designed to combat timestamp discontinuities (symptom: a naive FFmpeg run spews tons of "Non-monotonous DTS in output stream" warning messages and ends up with a useless file with completely broken timestamps).

`caterpillar` supports [up to version 3](https://tools.ietf.org/html/rfc8216#section-7) of the HTTP Live Streaming protocol (VOD only; non-VOD playlists are treated as VOD, and may result in unexpected consequences).

## Dependencies

A recent version of [FFmpeg](https://ffmpeg.org/download.html).

## Installation

Python 3.6 or later is required.

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
usage: caterpillar [-h] [-f] [-j JOBS] [-k]
                   [-m {concat_demuxer,concat_protocol,0,1}] [-v] [-q] [-V]
                   m3u8_url [output]

positional arguments:
  m3u8_url              the VOD URL
  output                path to the final output file (default is a .ts file
                        in the current directory with the basename of the VOD
                        URL)

optional arguments:
  -h, --help            show this help message and exit
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
  -v, --verbose         increase logging verbosity (can be specified multiple
                        times)
  -q, --quiet           decrease logging verbosity (can be specified multiple
                        times)
  -V, --version         show program's version number and exit
```

See the [wiki page](https://github.com/zmwangx/caterpillar/wiki/Usage-Examples) for usage examples.

## Notes

- **A note on `-m, --concat-method`**: The final step of `caterpillar` is concatenating one or more parts (generated from splitted playlists with FFmpeg's `hls` demuxer) into a single output file. In this step we provide two methods of choice: the [concat demuxer](https://ffmpeg.org/ffmpeg-all.html#concat-1) and the [concat protocol](https://ffmpeg.org/ffmpeg-all.html#concat-1) (the former is the default). To pick the non-default `concat_protocol`, specify `--concat-method concat_protocol` on the command line, or as a shortcut, `-m 1` (`0` is an alias for `concat_demuxer`, and `1` is an alias for `concat_protocol`).

  Each of these two methods may work better in certain cases. For instance, for [this stream](http://ts.snh48.com/chaoqing/8001/20171201185235-playlist.m3u8?beginTime=20171201205500&endTime=20171201210500), the concat demuxer simply fails with loads of error messages like "Application provided duration: 7980637472 / timestamp: 7994129672 is out of range for mov/mp4 format", whereas the concat protocol works fine. However, for [this stream](http://live.us.sinaimg.cn/000XDYqUjx07gRaRHSCz070d010002TZ0k01.m3u8), the concat protocol dumps a bunch of worrisome warnings like "DTS out of order" or "Non-monotonous DTS in output stream", whereas the concat demuxer doesn't.

  *In short, if the default fails you (either doesn't work outright, or the generated video is bad in some way), try `-m 1`.*

## Etymology

The word "caterpillar" starts with `cat(1)`, and the body of a caterpillar is segmented.

## Copyright

Copyright © 2017 Zhiming Wang

This project is licensed under [the MIT license](https://opensource.org/licenses/MIT). See `COPYING` for details.

[The image of the caterpillar](https://en.wikipedia.org/wiki/File:Chenille_de_Grand_porte_queue_(macaon).jpg) by Didier Descouens is distributed under the [Creative Commons Attribution-Share Alike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/) license.
