import logging
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional, Sequence

# import av  # type: ignore[import-untyped]
import pandas as pd
import PIL.Image

import pixeltable.exceptions as excs
import pixeltable.type_system as ts

from .base import ComponentIterator

_logger = logging.getLogger('pixeltable')


class FrameIterator(ComponentIterator):
    """
    Iterator over frames of a video. 
    DUMMY VERSION: Video extraction features disabled to avoid av dependency.
    """

    # Input parameters
    video_path: Path
    fps: Optional[float]
    num_frames: Optional[int]

    # Video info - DUMMY
    container: Any # av.container.input.InputContainer
    video_framerate: Fraction
    video_time_base: Fraction
    video_frame_count: int
    video_start_time: int

    # List of frame indices to be extracted, or None to extract all frames
    frames_to_extract: Optional[list[int]]

    # Next frame to extract
    next_pos: int

    def __init__(self, video: str, *, fps: Optional[float] = None, num_frames: Optional[int] = None):
         self.video_path = Path(video)
         self.fps = fps
         self.num_frames = num_frames
         # Dummy initialization
         self.video_frame_count = 0
         self.frames_to_extract = None
         self.next_pos = 0

    @classmethod
    def input_schema(cls) -> dict[str, ts.ColumnType]:
        return {
            'video': ts.VideoType(nullable=False),
            'fps': ts.FloatType(nullable=True),
            'num_frames': ts.IntType(nullable=True),
        }

    @classmethod
    def output_schema(cls, *args: Any, **kwargs: Any) -> tuple[dict[str, ts.ColumnType], list[str]]:
        return {
            'frame_idx': ts.IntType(),
            'pos_msec': ts.FloatType(),
            'pos_frame': ts.IntType(),
            'frame': ts.ImageType(),
        }, ['frame']

    def __next__(self) -> dict[str, Any]:
        raise StopIteration

    def close(self) -> None:
        pass

    def set_pos(self, pos: int) -> None:
        pass
