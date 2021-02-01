import pytest
import tsutils.subtitles
from tests import junjyoukirari_23_ts, invalid_ts, not_existing_ts

def test_Extract_Success():
    files = tsutils.subtitles.Extract(junjyoukirari_23_ts)
    assert len(files) == 2
    for path in files:
        path.unlink()

def test_Extract_Invalid():
    files = tsutils.subtitles.Extract(invalid_ts)
    assert len(files) == 0