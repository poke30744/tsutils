import pytest
import tsutils.common

def test_CheckExtenralCommand():
    tsutils.common.CheckExtenralCommand('ping')
    tsutils.common.CheckExtenralCommand('ping')
    with pytest.raises(tsutils.ProgramNotFound, match='aaa not found'):
        tsutils.common.CheckExtenralCommand('aaa')