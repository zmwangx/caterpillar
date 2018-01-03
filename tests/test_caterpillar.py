import os
import sys

import pytest

from caterpillar import caterpillar


pytestmark = pytest.mark.usefixtures('chtmpdir')


class TestCaterpillar(object):

    def test_default(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['-', hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert os.path.isfile('good.mp4')
        assert not os.path.exists('good')

    def test_output_file(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['-', hls_server.good_playlist, 'good.ts'])
        assert caterpillar.main() == 0
        assert os.path.isfile('good.ts')
        assert not os.path.exists('good')

    def test_formats(self, hls_server, monkeypatch):
        def try_extention(ext):
            output = f'good.{ext}'
            monkeypatch.setattr(sys, 'argv', ['-', hls_server.good_playlist, output])
            assert caterpillar.main() == 0
            assert os.path.isfile(output)

        try_extention('mp4')
        try_extention('ts')
        try_extention('mkv')
        try_extention('mov')
        try_extention('flv')

    def test_adts(self, hls_server, monkeypatch):
        def try_extention(ext):
            output = f'good.{ext}'
            monkeypatch.setattr(sys, 'argv', ['-', hls_server.adts_playlist, output])
            assert caterpillar.main() == 0
            assert os.path.isfile(output)

        try_extention('mp4')
        try_extention('ts')
        try_extention('mkv')
        try_extention('mov')
        try_extention('flv')

    def test_overwrite(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['-', hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert caterpillar.main() == 1
        monkeypatch.setattr(sys, 'argv', ['-', '-f', hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert os.path.isfile('good.mp4')
        assert not os.path.exists('good')

    def test_keep(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['-', '-k', hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert os.path.isfile('good.mp4')
        assert os.path.isdir('good')

    def test_empty_playlist(self, hls_server, monkeypatch, capfd):
        monkeypatch.setattr(sys, 'argv', ['-', hls_server.empty_playlist])
        assert caterpillar.main() == 1
        assert 'empty playlist' in capfd.readouterr().err
        assert os.path.isdir('empty')
        assert not os.path.isfile('empty.mp4')

    def test_containers(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['-', hls_server.good_playlist, 'good.flv'])
        assert caterpillar.main() == 0
        assert os.path.isfile('good.flv')
