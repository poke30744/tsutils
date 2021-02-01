import pytest
import tsutils.splitter
from tests import junjyoukirari_23_ts, invalid_ts, not_existing_ts

def test_Split_Success():
    splittedTs = tsutils.splitter.Split(junjyoukirari_23_ts)
    assert len(splittedTs) == 4
    # cleanup
    for path in splittedTs:
        path.unlink()

def test_Split_NotExisting():
    with pytest.raises(tsutils.TsFileNotFound, match='"not_existing.ts" not found!'):
        tsutils.splitter.Split(not_existing_ts)

def test_Split_Invalid():
    with pytest.raises(tsutils.InvalidTsFormat, match='"invalid.ts" is invalid!'):
        tsutils.splitter.Split(invalid_ts)

def test_Trim():
    trimmedTs = tsutils.splitter.Trim(junjyoukirari_23_ts)
    assert '_trimmed.ts' in str(trimmedTs)
    assert trimmedTs.stat().st_size > 1 * 1024 * 1024 * 1024