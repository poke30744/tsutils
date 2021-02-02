import re, subprocess, tempfile, argparse, shutil, json, pprint
from pathlib import Path
from tqdm import tqdm
import numpy as np
from PIL import Image
from .common import TsFileNotFound, InvalidTsFormat, CheckExtenralCommand

def GetInfoFromLines(lines):
    duration = 0
    programs = {}
    for line in lines:
        if 'Program ' in line:
            pid = line
            programs[pid] = { 'soundTracks' : 0 }
        elif 'Duration' in line:
            durationFields = line.split(',')[0].replace('Duration:', '').strip().split(':')
            duration = float(durationFields[0]) * 3600 + float(durationFields[1]) * 60  + float(durationFields[2])
        if 'Stream #' in line:
            if 'Video:' in line:
                for item in re.findall(r'\d+x\d+', line):
                    sizeFields = item.split('x')
                    if sizeFields[0] != '0' and sizeFields[1] != '0':
                        programs[pid]['width'], programs[pid]['height'] = int(sizeFields[0]), int(sizeFields[1])
                        break
                for item in line.split(','):
                    if ' fps' in item:
                        programs[pid]['fps'] = float(item.replace(' fps', ''))
                        break
                sar = line.split('SAR ')[1].split(' ')[0].split(':')
                sar = int(sar[0]), int(sar[1])
                dar = line.split('DAR ')[1].split(' ')[0].split(']')[0].split(':')
                dar = int(dar[0]), int(dar[1])
                programs[pid]['sar'] = sar
                programs[pid]['dar'] = dar
            elif 'Audio:' in line and 'Hz,' in line:
                programs[pid]['soundTracks'] += 1
        if 'Press [q] to stop' in line or ' time=' in line:
            break
    for pid in programs:
        if programs[pid]['soundTracks'] > 0:
            return {
                'duration': duration, 
                'width': programs[pid]['width'],
                'height': programs[pid]['height'],
                'fps': programs[pid]['fps'],
                'sar': programs[pid]['sar'],
                'dar': programs[pid]['dar'],
                'soundTracks': programs[pid]['soundTracks']
                }
    return None

def GetInfo(path):
    CheckExtenralCommand('ffmpeg')
    path = Path(path)
    if not path.is_file():
        raise TsFileNotFound(f'"{path.name}" not found!')
    pipeObj = subprocess.Popen(
        [
            'ffmpeg', '-hide_banner',
            # seek 30s to jump over the begining
            # over seeking is safe and will be ignored by ffmpeg
            '-ss', '30', '-i', path
        ], 
        stderr=subprocess.PIPE,
        universal_newlines=True,
        errors='ignore')
    info = GetInfoFromLines(pipeObj.stderr)
    pipeObj.wait()
    if info is None:
        raise InvalidTsFormat(f'"{path.name}" is invalid!')
    return info

def ExtractStream(path, output=None, ss=0, to=999999, toWav=False, quiet=False):
    CheckExtenralCommand('ffmpeg')
    path = Path(path)
    if not path.is_file():
        raise TsFileNotFound(f'"{path.name}" not found!')
    output = path.with_suffix('') if output is None else Path(output)
    if output.is_dir():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    
    info = GetInfo(path)

    args = [
            'ffmpeg', '-hide_banner', '-y',
            '-ss', str(ss), '-to', str(to), '-i', path,
            '-c:v', 'copy'
            ]
    # to sync corrputed sound tracks with the actual video length
    if toWav:
        args += [ '-af',  'aresample=async=1' ]
    
    # copy the video track
    args += [ '-map', '0:v:0', '-c:v', 'copy', output / 'video_0.ts' ]

    # copy audio tracks or decode to WAV
    extName = 'wav' if toWav else 'aac'
    for i in range(info['soundTracks']):
        args += [ '-map', f'0:a:{i}', output / f'audio_{i}.{extName}' ]

    pipeObj = subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
    info = GetInfoFromLines(pipeObj.stderr)
    if info is None:
        raise InvalidTsFormat(f'"{path.name}" is invalid!')
    with tqdm(total=info['duration'], unit='secs', disable=quiet) as pbar:
        pbar.set_description('Extracting streams')
        for line in pipeObj.stderr:
            if 'time=' in line:
                for item in line.split(' '):
                    if item.startswith('time='):
                        timeFields = item.replace('time=', '').split(':')
                        time = float(timeFields[0]) * 3600 + float(timeFields[1]) * 60  + float(timeFields[2])
                        pbar.update(time - pbar.n)
        pbar.update(info['duration'] - pbar.n)
    pipeObj.wait()
    return output

# more accurate than ExtractStream
def ExtractWav(path, output, ss=0, to=999999, quiet=False):
    pipeObj = subprocess.Popen(
        [
            'ffmpeg', '-hide_banner',
            '-ss', str(ss), '-to', str(to), '-i', path,
            '-af',  'aresample=async=1',
            '-f', 'wav', 
            '-y', output
        ]
        , stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
    info = GetInfoFromLines(pipeObj.stderr)
    with tqdm(total=info['duration'], unit='secs', disable=quiet) as pbar:
        pbar.set_description('Extracting wav')
        for line in pipeObj.stderr:
            if 'time=' in line:
                for item in line.split(' '):
                    if item.startswith('time='):
                        timeFields = item.replace('time=', '').split(':')
                        time = float(timeFields[0]) * 3600 + float(timeFields[1]) * 60  + float(timeFields[2])
                        pbar.update(time - pbar.n)
        pbar.update(info['duration'] - pbar.n)
    pipeObj.wait()

def ExtractFrameProps(path, ss, to, nosad=False):
    CheckExtenralCommand('ffmpeg')
    path = Path(path)
    if not path.is_file():
        raise TsFileNotFound(f'"{path.name}" not found!')
    with tempfile.TemporaryDirectory(prefix='logoNet_frames_') as tmpLogoFolder:
        args = [
            'ffmpeg', '-hide_banner',
            '-ss', str(ss), '-to', str(to),
            '-i', path,
            '-filter:v', "select='gte(t,0)',showinfo", '-vsync', '0', '-frame_pts', '1',
        ]
        if nosad:
            args += [
                '-f', 'null',
                '-'
            ]
        else:
            args += [
                f'{tmpLogoFolder}/out%8d.bmp'
        ]
        pipeObj = subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
        propList = []
        info = GetInfoFromLines(pipeObj.stderr)
        if info is None:
            raise InvalidTsFormat(f'"{path.name}" is invalid!')
        if to > info['duration']:
            to = info['duration']
        with tqdm(total=to - ss, unit='secs', disable=not nosad) as pbar:
            pbar.set_description('Extracting props')
            for line in pipeObj.stderr:
                if 'pts_time:' in line:
                    ptsTime = float(line.split('pts_time:')[1].lstrip().split(' ')[0])
                    pos = int(line.split('pos:')[1].lstrip().split(' ')[0])
                    checksum = line.split('checksum:')[1].split(' ')[0]
                    planeChecksum = line.split('plane_checksum:')[1].split('[')[1].split(']')[0].split(' ')
                    meanStrList = line.split('mean:')[1].split('\x08')[0].strip('[]').strip().split(' ')
                    stdevStrList = line.split('stdev:')[1].split('\x08')[0].strip('[]').strip().split(' ')
                    mean = [ float(i) for i in meanStrList ]
                    stdev = [ float(i) for i in stdevStrList ]
                    isKey = int(line.split(' iskey:')[1].split(' ')[0])
                    frameType = line.split(' type:')[1].split(' ')[0]
                    propList.append({
                        'ptsTime': ptsTime + ss,
                        'pos': pos,
                        'checksum': checksum,
                        'plane_checksum': planeChecksum,
                        'mean': mean,
                        'stdev': stdev,
                        'isKey': isKey,
                        'type': frameType,
                    })
                    pbar.update(ptsTime - pbar.n)
            pipeObj.wait()
            pbar.update(to - ss - pbar.n)
        if not nosad:
            pathList = sorted(list(Path(tmpLogoFolder).glob('*.bmp')))
            originalSize = Image.open(pathList[0]).size
            sadSize = round(originalSize[1] / 8), round(originalSize[0] / 8)
            imageList = [ np.array(Image.open(path).resize(sadSize, Image.NEAREST)) / 255.0 for path in pathList ]
        else:
            imageList = []
    for i, image in enumerate(imageList):
        if i == 0:
            sad = 0.0
        else:
            sad = np.sum(np.abs(image - imageList[i - 1])) / (sadSize[0] * sadSize[1] * 3)
        propList[i]['sad'] = sad
    for prop in propList[:]:
        if prop['ptsTime'] < ss or prop['ptsTime'] > to:
            propList.remove(prop)
    for prop in propList[:]:
        if prop['pos'] < 0:
            propList.remove(prop)
    return propList

def ExtractArea(path, area, folder, ss, to, fps='1/1', quiet=False):
    CheckExtenralCommand('ffmpeg')
    path = Path(path)
    if not path.is_file():
        raise TsFileNotFound(f'"{path.name}" not found!')

    folder = path.with_suffix('') if folder is None else Path(folder)
    if folder.is_dir():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    info = GetInfo(path)
    if info is None:
        raise InvalidTsFormat(f'"{path.name}" is invalid!')
    w, h, x, y = int(round(area[2] * info['width'])), int(round(area[3] * info['height'])), int(round(area[0] * info['width'])), int(round(area[1] * info['height']))
    args = [ 'ffmpeg', '-hide_banner' ]
    if ss is not None and to is not None:
        args += [ '-ss', str(ss), '-to', str(to) ]
    fpsStr = ',fps={}'.format(fps) if fps else ''
    args += [
        '-i', path,
        '-filter:v', 'crop={}:{}:{}:{}{}'.format(w, h, x, y, fpsStr),
        '{}/out%8d.bmp'.format(folder) ]
    pipeObj = subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
    with tqdm(total=info['duration'], disable=quiet, unit='secs') as pbar:
        pbar.set_description('Extracting area')
        for line in pipeObj.stderr:
            if 'time=' in line:
                for item in line.split(' '):
                    if item.startswith('time='):
                        timeFields = item.replace('time=', '').split(':')
                        time = float(timeFields[0]) * 3600 + float(timeFields[1]) * 60  + float(timeFields[2])
                        pbar.update(time - pbar.n)
        pbar.update(info['duration'] - pbar.n)
    pipeObj.wait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Python wrapper of ffmpeg')
    parser.add_argument('--quiet', '-q', action='store_true', help="don't output to the console")
    subparsers = parser.add_subparsers(required=True, title='subcommands', dest='command')

    subparser = subparsers.add_parser('info', help='mark CM clips in the mpegts file')
    subparser.add_argument('--input', '-i', required=True, help='input mpegts path')

    subparser = subparsers.add_parser('stream', help='extract video and audio streams from the mpegts file')
    subparser.add_argument('--input', '-i', required=True, help='input mpegts path')
    subparser.add_argument('--output', '-o', help='output folder path')

    subparser = subparsers.add_parser('area', help='extract video area as pictures')
    subparser.add_argument('--input', '-i', required=True, help='input mpegts path')
    subparser.add_argument('--output', '-o', help='output folder path')
    subparser.add_argument('--area', default=[0.0, 0.0, 1.0, 1.0], nargs=4, type=float, help='the area to extract')
    subparser.add_argument('--ss', type=float, default=999999, help='from (seconds)')
    subparser.add_argument('--to', type=float, default=0, help='to (seconds)')
    subparser.add_argument('--fps', default='1/1', help='fps like 1/1')

    subparser = subparsers.add_parser('props', help='extract frame properties')
    subparser.add_argument('--input', '-i', required=True, help='input mpegts path')
    subparser.add_argument('--ss', type=float, default=999999, help='from (seconds)')
    subparser.add_argument('--to', type=float, default=0, help='to (seconds)')

    args = parser.parse_args()

    if args.command == 'info':
        info = GetInfo(path=args.input)
        print("info:", info)
    elif args.command == 'stream':
        ExtractStream(path=args.input, toWav=True)
    elif args.command == 'area':
        ExtractArea(path=args.input, area=args.area, folder=args.output, ss=args.ss, to=args.to, fps=args.fps)
    elif args.command == 'props':
        props = ExtractFrameProps(path=args.input, ss=args.ss, to=args.to)
        pp = pprint.PrettyPrinter()
        pp.pprint(props)