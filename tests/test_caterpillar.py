import os
import re
import pathlib
import subprocess
import sys

import pytest

from caterpillar import caterpillar
from caterpillar.events import EventType


pytestmark = pytest.mark.usefixtures("chtmpdir")


# Returns ffprobe output for the specified media file.
def probe(file):
    return subprocess.check_output(
        ["ffprobe", "-hide_banner", file],
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )


class TestCaterpillar(object):
    def test_default(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["-", hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert os.path.isfile("good.mp4")
        assert not os.path.exists("good")

    def test_output_file(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["-", hls_server.good_playlist, "good.ts"])
        assert caterpillar.main() == 0
        assert os.path.isfile("good.ts")
        assert not os.path.exists("good")

    @pytest.mark.parametrize(
        "mode,adts", [("0", False), ("0", True), ("1", False), ("1", True)]
    )
    def test_formats(self, hls_server, monkeypatch, mode, adts):
        playlist = hls_server.adts_playlist if adts else hls_server.good_playlist

        def try_extention(ext):
            output = f"good.{ext}"
            monkeypatch.setattr(sys, "argv", ["-", "-m", mode, playlist, output])
            assert caterpillar.main() == 0
            assert os.path.isfile(output)

        try_extention("mp4")
        try_extention("ts")
        try_extention("mkv")
        try_extention("mov")
        try_extention("flv")

    def test_overwrite(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["-", hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert caterpillar.main() == 1
        monkeypatch.setattr(sys, "argv", ["-", "-f", hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert os.path.isfile("good.mp4")
        assert not os.path.exists("good")

    def test_keep(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["-", "-k", hls_server.good_playlist])
        assert caterpillar.main() == 0
        assert os.path.isfile("good.mp4")
        assert os.path.isdir("good")

    def test_empty_playlist(self, hls_server, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["-", hls_server.empty_playlist])
        assert caterpillar.main() == 1
        assert os.path.isdir("empty")
        assert not os.path.isfile("empty.mp4")

    def test_variant_streams(self, hls_server, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["-", hls_server.variants_playlist, "variant.mp4"]
        )
        assert caterpillar.main() == 0
        assert os.path.isfile("variant.mp4")
        # Make sure the 720p variant is the one downloaded, not the 480p one.
        assert re.search(r"Video:.*1280x720", probe("variant.mp4"))

    def test_event_hooks(self, hls_server):
        seen_event_types = set()

        def event_hook(event):
            seen_event_types.add(event.event_type)

        assert (
            caterpillar.process_entry(
                hls_server.good_playlist,
                pathlib.Path("good.mp4"),
                event_hooks=[event_hook],
            )
            == 0
        )
        assert os.path.isfile("good.mp4")
        assert seen_event_types >= set(
            [
                EventType.SEGMENTS_DOWNLOAD_INITIATED,
                EventType.SEGMENT_DOWNLOAD_SUCCEEDED,
                EventType.SEGMENTS_DOWNLOAD_FINISHED,
                EventType.MERGE_FINISHED,
            ]
        )
