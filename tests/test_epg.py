from pathlib import Path
import pytest
import tsutils.epg
from tests import junjyoukirari_23_ts, invalid_ts, not_existing_ts

def test_DumpEPG_Success():
    epgPath, txtPath = tsutils.epg.Dump(junjyoukirari_23_ts)
    assert epgPath.is_file() and txtPath.is_file()
    # cleanup
    epgPath.unlink()
    txtPath.unlink()

def test_DumpEPG_Invalid():
    with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        tsutils.epg.Dump(invalid_ts)