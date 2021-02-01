import sys, subprocess
from pathlib import Path
import pysubs2
from .common import TsFileNotFound, InvalidTsFormat, CheckExtenralCommand

def Extract(path):
    CheckExtenralCommand('LEProc2')
    caption2AssPath = CheckExtenralCommand('Caption2AssC')
    path = Path(path)
    if not path.is_file():
        raise TsFileNotFound(f'"{path.name}" not found!')
    subtitlesPathes = [ Path(path).with_suffix(ext) for ext in ( '.srt','.ass' ) ]
    for subtitlePath in subtitlesPathes:
        if subtitlePath.exists():
            subtitlePath.unlink()
    retry = 0
    while any([ not path.exists() for path in subtitlesPathes ]) and retry < 2:
        pipeObj = subprocess.Popen(
            [
                "LEProc2.exe", # to emulate CP932 by Locale Emulator
                caption2AssPath,
                '-format', 'dual',
                path
            ], stdout=subprocess.PIPE)
        _ = pipeObj.stdout.readlines()
        pipeObj.wait()
        retry += 1
    for subtitlesPath in subtitlesPathes:
        if subtitlesPath.exists():
            if subtitlesPath.stat().st_size == 0:
                subtitlesPath.unlink()
            else:
                # trying to fix syntax issues of Caption2AssC.exe
                subtitles = pysubs2.load(subtitlesPath, encoding='utf-8')
                subtitles.save(subtitlesPath)
    return [ path for path in subtitlesPathes if path.exists() ]