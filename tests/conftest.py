import http.server
import multiprocessing
import os
import shutil
import subprocess
import signal
import tempfile

import pytest


class HLSServer(http.server.HTTPServer, multiprocessing.Process):

    def __init__(self):
        address = ('127.0.0.1', 0)
        handler = http.server.SimpleHTTPRequestHandler
        http.server.HTTPServer.__init__(self, address, handler)
        multiprocessing.Process.__init__(self)

        host, port = self.socket.getsockname()
        self.server_root = f'http://{host}:{port}/'
        self.good_playlist = self.server_root + 'good.m3u8'
        self.empty_playlist = self.server_root + 'empty.m3u8'
        self.adts_playlist = self.server_root + 'adts.m3u8'

        self.tmpdir = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            # Generate good.m3u8
            subprocess.run('ffmpeg -loglevel warning '
                           '-f rawvideo -s hd720 -pix_fmt yuv420p -r 30 -t 30 -i /dev/zero '
                           '-f hls -hls_playlist_type vod -y good.m3u8', shell=True)
            # Generate adts.m3u8 (AAC stream with ADTS headers)
            subprocess.run('ffmpeg -loglevel warning '
                           '-f lavfi -i anullsrc -t 30 -f adts -y adts.aac', shell=True)
            subprocess.run('ffmpeg -loglevel warning '
                           '-i adts.aac -f hls -hls_playlist_type vod -y adts.m3u8', shell=True)
            # Generate empty.m3u8
            with open('empty.m3u8', 'w') as fp:
                fp.write('#EXTM3U\n'
                         '#EXT-X-VERSION:3\n'
                         '#EXT-X-TARGETDURATION:5\n'
                         '#EXT-X-ENDLIST\n')
        finally:
            os.chdir(cwd)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        os.kill(self.pid, signal.SIGINT)

    def run(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.tmpdir)
            self.serve_forever()
        except KeyboardInterrupt:
            self.shutdown()
            self.server_close()
            self.teardown()
        finally:
            os.chdir(cwd)

    def teardown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass


@pytest.fixture(scope='session')
def hls_server():
    with HLSServer() as server:
        yield server


@pytest.fixture()
def chtmpdir(tmpdir_factory):
    cwd = os.getcwd()
    tmpdir = tmpdir_factory.mktemp('test')
    try:
        os.chdir(tmpdir)
        yield tmpdir
    finally:
        os.chdir(cwd)
