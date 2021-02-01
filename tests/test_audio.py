import pytest
import tsutils.audio
from tests import junjyoukirari_23_ts, invalid_ts, not_existing_ts

def test_DetectSilence_Success():
    periods = tsutils.audio.DetectSilence(junjyoukirari_23_ts, 0, 120)
    assert len(periods) > 0

def test_DetectSilence_Invalid():
     with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        tsutils.audio.DetectSilence(invalid_ts)