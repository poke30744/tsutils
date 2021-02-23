import subprocess, shutil
from pathlib import Path
from .common import TsFileNotFound, InvalidTsFormat, CheckExtenralCommand

TRIM_THRESHOLD = 10 * 1024 * 1024
BUF_SIZE = 1024 * 1024

def Split(videoPath):
    CheckExtenralCommand('TsSplitter')
    videoPath = Path(videoPath).absolute()
    if not videoPath.is_file():
        raise TsFileNotFound(f'"{videoPath.name}" not found!')
    cmdLine = f'TsSplitter -EIT -ECM -EMM -SD -1SEG -SEP3 -SEPA "{videoPath}"'
    pipeObj = subprocess.Popen(cmdLine)
    pipeObj.wait()
    splittedTs1 = [ path for path in videoPath.parent.glob('*.ts') if path.stem.startswith(videoPath.stem + '_') ]
    splittedTs2 = [ path for path in splittedTs1 if '_HD' in path.stem or '_CS' in path.stem ]
    splittedTs = sorted(splittedTs2, key=lambda x: x.stem)
    if len(splittedTs) == 0:
        raise InvalidTsFormat(f'"{videoPath.name}" is invalid!')
    return splittedTs

def Trim(videoPath, outputPath=None):
    splittedTs = Split(videoPath)
    while True:
        if splittedTs[0].stat().st_size < TRIM_THRESHOLD:
            splittedTs[0].unlink()
            del splittedTs[0]
        elif splittedTs[-1].stat().st_size < TRIM_THRESHOLD:
            splittedTs[-1].unlink()
            del splittedTs[-1]
        else:
            break
    outputPath = Path(outputPath) if outputPath is not None else Path(str(videoPath).replace('.ts', '_trimmed.ts'))
    with outputPath.open('wb') as wf:
        for path in splittedTs:
            with path.open('rb') as rf:
                while True:
                    data = rf.read(BUF_SIZE)
                    if len(data) == 0:
                        break
                    wf.write(data)
            path.unlink()
    return outputPath