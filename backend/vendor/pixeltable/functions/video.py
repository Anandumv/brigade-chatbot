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
from typing import Optional

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
    #'mp4': ('aac', 'm4a'),
}

# Values for mp4 fix commented out

@pxt.uda(requires_order_by=True)
class make_video(pxt.Aggregator):
    """
    Aggregator that creates a video from a sequence of images.
    """
    def __init__(self, fps: int = 25):
        pass

    def update(self, frame: PIL.Image.Image) -> None:
        pass

    def value(self) -> str: # pxt.Video:
        return ""


@pxt.udf(is_method=True)
def extract_audio(
    video_path: str, stream_idx: int = 0, format: str = 'wav', codec: Optional[str] = None
) -> str: # pxt.Audio:
    return ""


@pxt.udf(is_method=True)
def get_metadata(video: str) -> dict: # pxt.Video) -> dict:
    return {}


def _get_metadata(path: str) -> dict:
    return {}


def __get_stream_metadata(stream: Any) -> dict:
    return {}

    codec_context = stream.codec_context
    codec_context_md = {
        'name': codec_context.name,
        'codec_tag': codec_context.codec_tag.encode('unicode-escape').decode('utf-8'),
        'profile': codec_context.profile,
    }
    metadata = {
        'type': stream.type,
        'duration': stream.duration,
        'time_base': float(stream.time_base) if stream.time_base is not None else None,
        'duration_seconds': float(stream.duration * stream.time_base)
        if stream.duration is not None and stream.time_base is not None
        else None,
        'frames': stream.frames,
        'metadata': stream.metadata,
        'codec_context': codec_context_md,
    }

    if stream.type == 'audio':
        # Additional metadata for audio
        codec_context_md['channels'] = int(codec_context.channels) if codec_context.channels is not None else None
    else:
        assert stream.type == 'video'
        # Additional metadata for video
        codec_context_md['pix_fmt'] = getattr(stream.codec_context, 'pix_fmt', None)
        metadata.update(
            **{
                'width': stream.width,
                'height': stream.height,
                'frames': stream.frames,
                'average_rate': float(stream.average_rate) if stream.average_rate is not None else None,
                'base_rate': float(stream.base_rate) if stream.base_rate is not None else None,
                'guessed_rate': float(stream.guessed_rate) if stream.guessed_rate is not None else None,
            }
        )

    return metadata


__all__ = local_public_names(__name__)


def __dir__():
    return __all__
