"""
Pixeltable [UDFs](https://pixeltable.readme.io/docs/user-defined-functions-udfs) for `VideoType`.

Example:
```python
import pixeltable as pxt
from pixeltable.functions import video as pxt_video

t = pxt.get_table(...)
t.select(pxt_video.extract_audio(t.video_col)).collect()
```
"""

import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

# import av  # type: ignore[import-untyped]
import numpy as np
import PIL.Image

import pixeltable as pxt
import pixeltable.env as env
from pixeltable.utils.code import local_public_names

_format_defaults = {  # format -> (codec, ext)
    'wav': ('pcm_s16le', 'wav'),
    'mp3': ('libmp3lame', 'mp3'),
    'flac': ('flac', 'flac'),
}


@pxt.uda(requires_order_by=True)
class make_video(pxt.Aggregator):
    """
    Aggregator that creates a video from a sequence of images.
    NOTE: Disabled - video features require av/FFmpeg.
    """
    def __init__(self, fps: int = 25):
        pass

    def update(self, frame: PIL.Image.Image) -> None:
        pass

    def value(self) -> str:
        return ""


@pxt.udf(is_method=True)
def extract_audio(
    video_path: str, stream_idx: int = 0, format: str = 'wav', codec: Optional[str] = None
) -> str:
    """Disabled - video features require av/FFmpeg."""
    return ""


@pxt.udf(is_method=True)
def get_metadata(video: str) -> dict:
    """Disabled - video features require av/FFmpeg."""
    return {}


def _get_metadata(path: str) -> dict:
    return {}


def __get_stream_metadata(stream: Any) -> dict:
    return {}


__all__ = local_public_names(__name__)


def __dir__():
    return __all__
