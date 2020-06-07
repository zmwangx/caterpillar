import m3u8

from typing import Tuple


# Rate variant stream by resolution, average bandwidth, and bandwidth.
def variant_score(variant: m3u8.Playlist) -> Tuple[int, int, int, int]:
    stream_info = variant.stream_info
    if stream_info.resolution:
        width, height = stream_info.resolution
    else:
        width = height = 0
    average_bandwidth = stream_info.average_bandwidth or 0
    bandwidth = stream_info.bandwidth or 0
    return (width, height, average_bandwidth, bandwidth)


# Select the best variant stream (best effort).
#
# Assumption: m3u8 object has one or more variants.
def select_variant(m3u8_obj: m3u8.M3U8) -> m3u8.Playlist:
    return sorted(m3u8_obj.playlists, key=variant_score, reverse=True)[0]
