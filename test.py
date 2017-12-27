#!/usr/bin/env python3
import caterpillar.download
from caterpillar.utils import logger, increase_logging_verbosity
import pathlib
# increase_logging_verbosity(-2)
caterpillar.download.download_m3u8_segments('http://live.us.sinaimg.cn/001IfIqLjx07gRFya9sz070d010002vV0k01.m3u8',
                                            pathlib.Path('/tmp/yizhibo/remote.m3u8'),
                                            pathlib.Path('/tmp/yizhibo/local.m3u8'))
