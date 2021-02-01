import pytest, tempfile, os
import tsutils.ffmpeg
from tests import junjyoukirari_23_ts, invalid_ts, not_existing_ts

def test_GetInfo_Success():
    info = tsutils.ffmpeg.GetInfo(junjyoukirari_23_ts)
    assert info['duration'] == 902.22

def test_GetInfo_NotExisting():
    with pytest.raises(tsutils.TsFileNotFound, match='"not_existing.ts" not found!'):
        tsutils.ffmpeg.GetInfo(not_existing_ts)

def test_GetInfo_Invalid():
    with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        tsutils.ffmpeg.GetInfo(invalid_ts)

def test_ExtractWav_Success():
    path = tsutils.ffmpeg.ExtractWav(junjyoukirari_23_ts)
    assert path.stat().st_size > 1 * 1024 * 1024
    path.unlink()

def test_ExtractWav_Invalid():
    with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        tsutils.ffmpeg.ExtractWav(invalid_ts)

def test_ExtractFrameProps_Success():
    props = tsutils.ffmpeg.ExtractFrameProps(junjyoukirari_23_ts, 0, 2)
    assert len(props) > 0

def test_ExtractFrameProps_Invalid():
    with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        tsutils.ffmpeg.ExtractFrameProps(invalid_ts, 0, 2)

def test_ExtractArea_Success():
    with tempfile.TemporaryDirectory(prefix='test_ExtractArea') as tmpFolder:
        tsutils.ffmpeg.ExtractArea(junjyoukirari_23_ts, (0.2, 0.2, 0.8, 0.8), tmpFolder, 10, 20)
        assert len(os.listdir(tmpFolder)) > 0

def test_ExtractArea_Invalid():
    with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        with tempfile.TemporaryDirectory(prefix='test_ExtractArea') as tmpFolder:
            tsutils.ffmpeg.ExtractArea(invalid_ts, (0.2, 0.2, 0.8, 0.8), tmpFolder, 10, 20)