<h1 align="center">Caterpillar</h1>

<p align="center"><img src="https://user-images.githubusercontent.com/4149852/34367011-a9b11be8-ea72-11e7-8a96-ce34dae1eb0f.jpg" alt="Caterpillar" width="400" height="242"></p>

`caterpillar` is a hardened HLS merger. It takes an HTTP Live Streaming VOD URL (typically an .m3u8 URL), downloads the video segments, and attempts to merge them into a single, coherent file. It is specially designed to combat timestamp discontinuities (symptom: a naive FFmpeg run spews tons of "Non-monotonous DTS in output stream" warning messages and ends up with a useless file with completely broken timestamps).

`caterpillar` supports [up to version 3](https://tools.ietf.org/html/rfc8216#section-7) of the HTTP Live Streaming protocol (VOD only; non-VOD playlists are treated as VOD, and may result in unexpected consequences).

## Dependencies

A recent version of [FFmpeg](https://ffmpeg.org/download.html).

## Installation

```
git clone https://github.com/zmwangx/caterpillar.git
cd caterpillar
python3 setup.py develop
caterpillar -h
```

## Usage

```console
$ caterpillar -h
usage: caterpillar [-h] [-f] [-j JOBS] [-v] [-q] [-V] m3u8_url output

positional arguments:
  m3u8_url              the VOD URL
  output                path to the final output file

optional arguments:
  -h, --help            show this help message and exit
  -f, --force           overwrite the output file if it already exists
  -j JOBS, --jobs JOBS  maximum number of concurrent downloads (default is
                        twice the number of CPU cores, including virtual
                        cores)
  -v, --verbose         increase logging verbosity (can be specified multiple
                        times)
  -q, --quiet           decrease logging verbosity (can be specified multiple
                        times)
  -V, --version         show program's version number and exit
```

## Etymology

The word "caterpillar" starts with `cat(1)`, and the body of a caterpillar is segmented.

## Copyright

Copyright © 2017 Zhiming Wang

This project is licensed under [the MIT license](https://opensource.org/licenses/MIT). See `COPYING` for details.

[The image of the caterpillar](https://en.wikipedia.org/wiki/File:Chenille_de_Grand_porte_queue_(macaon).jpg) by Didier Descouens is distributed under the [Creative Commons Attribution-Share Alike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/) license.
