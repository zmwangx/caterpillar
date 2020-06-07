import http.server
import multiprocessing
import os
import shutil
import subprocess
import signal
import tempfile

import pytest


class HLSServer(http.server.HTTPServer):
    def __init__(self):
        address = ("127.0.0.1", 0)
        handler = http.server.SimpleHTTPRequestHandler
        super().__init__(address, handler)

        host, port = self.socket.getsockname()
        self.server_root = f"http://{host}:{port}/"
        self.good_playlist = self.server_root + "good.m3u8"
        self.empty_playlist = self.server_root + "empty.m3u8"
        self.adts_playlist = self.server_root + "adts.m3u8"
        self.variants_playlist = self.server_root + "variants.m3u8"

        self.tmpdir = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            # Generate good.m3u8
            subprocess.run(
                "ffmpeg -loglevel warning "
                "-f rawvideo -s hd720 -pix_fmt yuv420p -r 30 -t 30 -i /dev/zero "
                "-f hls -hls_playlist_type vod -y good.m3u8",
                shell=True,
                check=True,
            )
            # Generate adts.m3u8 (AAC stream with ADTS headers)
            subprocess.run(
                "ffmpeg -loglevel warning "
                "-f lavfi -i anullsrc -t 30 -f adts -y adts.aac",
                shell=True,
                check=True,
            )
            subprocess.run(
                "ffmpeg -loglevel warning "
                "-i adts.aac -f hls -hls_playlist_type vod -y adts.m3u8",
                shell=True,
                check=True,
            )
            # Generate empty.m3u8
            with open("empty.m3u8", "w", encoding="utf-8") as fp:
                fp.write(
                    "#EXTM3U\n"
                    "#EXT-X-VERSION:3\n"
                    "#EXT-X-TARGETDURATION:5\n"
                    "#EXT-X-ENDLIST\n"
                )
            # Generate variants.m3u8
            subprocess.run(
                "ffmpeg -loglevel warning "
                "-f rawvideo -s hd720 -pix_fmt yuv420p -r 30 -t 30 -i /dev/zero "
                "-map 0:0 -map 0:0 "
                "-s:v:0 hd480 -b:v:0 500k "
                "-s:v:1 hd720 -b:v:1 1000k "
                "-f hls "
                "-var_stream_map 'v:0 v:1' "
                "-master_pl_name variants.m3u8 "
                "-hls_playlist_type vod "
                "variant-%v/index.m3u8",
                shell=True,
                check=True,
            )
        finally:
            os.chdir(cwd)

    def teardown(self):
        self.shutdown()
        self.server_close()
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass


class HLSServerProcess(multiprocessing.Process):
    def __init__(self):
        super().__init__()
        self._queue = multiprocessing.Queue()

    def run(self):
        try:
            server = HLSServer()
            self._queue.put(
                (
                    dict(
                        server_root=server.server_root,
                        good_playlist=server.good_playlist,
                        empty_playlist=server.empty_playlist,
                        adts_playlist=server.adts_playlist,
                        variants_playlist=server.variants_playlist,
                        tmpdir=server.tmpdir,
                    ),
                    None,
                )
            )
        except Exception as exc:
            self._queue.put((None, exc))
            return
        cwd = os.getcwd()
        try:
            os.chdir(server.tmpdir)
            server.serve_forever()
        except KeyboardInterrupt:
            server.teardown()
        finally:
            os.chdir(cwd)

    def __enter__(self):
        self.start()
        conf, exc = self._queue.get()
        if exc:
            raise exc
        self.__dict__.update(**conf)
        return self

    def __exit__(self, *_):
        os.kill(self.pid, signal.SIGINT)


@pytest.fixture(scope="session")
def hls_server():
    with HLSServerProcess() as server:
        yield server


@pytest.fixture()
def chtmpdir(tmpdir_factory):
    cwd = os.getcwd()
    tmpdir = tmpdir_factory.mktemp("test")
    try:
        os.chdir(tmpdir)
        yield tmpdir
    finally:
        os.chdir(cwd)
