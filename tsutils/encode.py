import sys, subprocess, shutil, tempfile, argparse
from pathlib import Path
import numpy as np
from tqdm import tqdm
from PIL import Image
from .ffmpeg import GetInfo, GetInfoFromLines, ExtractArea, ExtractStream

def FindVideoBox(path, ss=None, to=None, quiet=False):
    info = GetInfo(path)
    if ss is None or to is None:
        ss, to = 0, info['duration']
    with tempfile.TemporaryDirectory(prefix='aspect_ratio_') as tmpLogoFolder:
        ExtractArea(path, (0.0, 0.0, 1.0, 1.0), tmpLogoFolder, ss, to, fps=100 / (to - ss), quiet=quiet)
        pics = sorted(list(Path(tmpLogoFolder).glob('*.bmp')))
        delta_0 = np.zeros((info['height'], info['width'], 3))
        for i in range(len(pics) - 1):
            image1 = np.array(Image.open(pics[i])).astype(np.float32) / 255.0
            image2 = np.array(Image.open(pics[i + 1])).astype(np.float32) / 255.0
            delta_0 += np.absolute(image1 - image2)
        delta_0 /= len(pics) - 1
    delta = (np.mean(delta_0, axis=2) > 0.1) * 1.0
    width, height = delta_0.shape[0], delta_0.shape[1]
    centerX, centerY = width // 2, height // 2
    for x1 in range(centerX, 0, -1):
        if delta[x1][centerY] == 0.0:
            break
    x1 += 1
    for y1 in range(centerY, 0, -1):
        if delta[centerX][y1] == 0.0:
            break
    y1 += 1
    for x2 in range(centerX, width, 1):
        if delta[x2][centerY] == 0.0:
            break
    x2 -= 1
    for y2 in range(centerY, height, 1):
        if delta[centerX][y2] == 0.0:
            break
    y2 -= 1
    return y1, x1, y2 - y1 + 1, x2 - x1 + 1

presets = {
    'drama': {
        'videoFilter': 'bwdif=0',
        'bitrate': '5000k',
        'maxRate': '2500k',
    },
    'drama720p': {
        'videoFilter': 'bwdif=0,scale=1280:720',
        'bitrate': '1500k',
        'maxRate': '3000k',
    },
    'anime': {
        'videoFilter': 'pullup,fps=24000/1001',
        'bitrate': '5000k',
        'maxRate': '2500k',
    },
    'anime720p': {
        'videoFilter': 'pullup,fps=24000/1001,scale=1280:720',
        'bitrate': '1500k',
        'maxRate': '3000k',
    },
    'anime480p': {
        'videoFilter': 'pullup,fps=24000/1001,scale=852:480',
        'bitrate': '750k',
        'maxRate': '1500k',
    },
}

def GetAudioLanguagesByName(name):
    if '[二]' in name:
        audioLanguages = ['jpn', 'eng']
    elif '[解]' in name:
        audioLanguages = ['jpn', 'jpn']
    elif '[多]' in name:
        audioLanguages = ['jpn', 'jpn']
    else:
        audioLanguages = ['jpn']
    return audioLanguages

def StripTS(videoPath, outputPath=None, audioLanguages=None, nomap=False, quiet=False):
    videoPath = Path(videoPath)
    outputPath = Path(outputPath) if outputPath else videoPath.with_name(videoPath.name.replace('.ts', '_stripped.ts'))
    if outputPath.exists() and videoPath.stat().st_mtime == outputPath.stat().st_mtime:
        print(f'Skipping stripping {videoPath.name}', file=sys.stderr)
        return outputPath
    info = GetInfo(videoPath)
    duration = info['duration']
    soundTracks = info['soundTracks']
    audioLanguages = GetAudioLanguagesByName(videoPath.name) if audioLanguages is None else audioLanguages
    args = [
        'ffmpeg', '-hide_banner', '-y',
        '-i', str(videoPath),
        '-c', 'copy'
    ]
    if not nomap:
        args += [ '-map', '0:v', '-map', '0:a', '-ignore_unknown' ]
        for i in range(soundTracks):
            args += [ f'-metadata:s:a:{i}', f'language={audioLanguages[i]}' ]
    args += [ str(outputPath) ]
    pipeObj = subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
    output = []
    with tqdm(total=duration, unit='secs', disable=quiet) as pbar:
        pbar.set_description('StripTS')
        for line in pipeObj.stderr:
            output.append(line)
            if 'time=' in line:
                for item in line.split(' '):
                    if item.startswith('time='):
                        timeFields = item.replace('time=', '').split(':')
                        time = float(timeFields[0]) * 3600 + float(timeFields[1]) * 60  + float(timeFields[2])
                        pbar.update(time - pbar.n)
        pbar.update(duration - pbar.n)
    pipeObj.wait()
    shutil.copystat(videoPath, outputPath)
    return outputPath

def StripAndRepackTS(videoPath, outputPath=None, audioLanguages=None, quiet=False):
    videoPath = Path(videoPath)
    outputPath = Path(outputPath) if outputPath else videoPath.with_name(videoPath.name.replace('.ts', '_stripped.ts'))
    if outputPath.exists() and videoPath.stat().st_mtime == outputPath.stat().st_mtime:
        print(f'Skipping stripping {videoPath.name}', file=sys.stderr)
        return outputPath

    info = GetInfo(videoPath)
    duration = info['duration']
    soundTracks = info['soundTracks']
    audioLanguages = GetAudioLanguagesByName(videoPath.name) if audioLanguages is None else audioLanguages

    streamsFolder = ExtractStream(path=videoPath, toWav=True)

    args = [ 'ffmpeg', '-hide_banner', '-y' ]
    # video stream
    args += [ '-i', streamsFolder / 'video_0.ts' ]
    # audio streams
    for i in range(soundTracks):
        args += [ '-i', streamsFolder / f'audio_{i}.wav' ]
    # maps
    for i in range(soundTracks + 1):
        args += [ '-map', f'{i}' ]
    # language tags
    for i in range(soundTracks):
        args += [ f'-metadata:s:a:{i}', f'language={audioLanguages[i]}' ]
    # encoders
    args += [ '-c:v', 'copy', '-c:a', 'aac' ]
    # output path
    args += [ outputPath ]

    pipeObj = subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
    output = []
    with tqdm(total=duration, unit='secs', disable=quiet) as pbar:
        pbar.set_description('StripTS2')
        for line in pipeObj.stderr:
            output.append(line)
            if 'time=' in line:
                for item in line.split(' '):
                    if item.startswith('time='):
                        timeFields = item.replace('time=', '').split(':')
                        time = float(timeFields[0]) * 3600 + float(timeFields[1]) * 60  + float(timeFields[2])
                        pbar.update(time - pbar.n)
        pbar.update(duration - pbar.n)
    pipeObj.wait()
    shutil.rmtree(streamsFolder)
    shutil.copystat(videoPath, outputPath)
    return outputPath

def EncodeTS(videoPath, preset, cropdetect, encoder, crf, outputPath=None, notag=False, quiet=False):
    videoPath = Path(videoPath)
    if outputPath is None:
        outputPath = videoPath.with_suffix('.mp4') if notag else videoPath.with_suffix(f'.{preset}_{encoder}_crf{crf}.mp4')
    outputPath = Path(outputPath)
    if outputPath.exists() and videoPath.stat().st_mtime == outputPath.stat().st_mtime:
        print(f'Skipping encoding {videoPath.name}', file=sys.stderr)
        return outputPath
    preset = presets[preset]
    videoFilter = preset['videoFilter']
    if cropdetect:
        info = GetInfo(videoPath)
        sar = info['sar']
        x, y, w, h = FindVideoBox(videoPath)
        for dar in ((16, 9), (4, 3), (1,1), (999, 999)):
            if 0.95 < w * sar[0] / (h * sar[1]) / (dar[0] / dar[1]) < 1.05:
                break
        zoomRate = w * h / (info['width'] * info['height'])
        if dar[0] != 999 and zoomRate < 0.9:
            filters = preset['videoFilter'].split(',')
            cropStr = f'crop={w}:{h}:{x}:{y},setdar=dar={dar[0]}/{dar[1]}'
            filters.insert(0, cropStr)
            if 'scale=' in filters[-1]:
                scale = filters.pop().replace('scale=', '').split(':')
                scale_h = int(scale[1])
                scale_w = round(scale_h * dar[0] * sar[1] / dar[1] / sar[0])
                filters.append(f'scale={scale_w}:{scale_h}')
            else:
                scale_h = round(h / dar[1] / sar[0]) * dar[1] * sar[0]
                scale_w = round(scale_h * dar[0] * sar[1] / dar[1] / sar[0])
                filters.append(f'scale={scale_w}:{scale_h}')
            videoFilter = ','.join(filters)
            print(f'cropping using: "{cropStr}"', file=sys.stderr)
        else:
            print('No need to crop.', file=sys.stderr)
    if '_nvenc' in encoder:
        videoCodec = [ '-c:v', encoder, '-rc:v', 'vbr_hq', '-cq:v', str(crf), '-b:v', preset['bitrate'], '-maxrate:v', preset['maxRate'], '-profile:v', 'high' ]
    elif '_videotoolbox' in encoder:
        videoCodec = [ '-c:v', encoder, '-b:v', preset['bitrate'], '-maxrate:v',  preset['maxRate'] ]
    else:
        videoCodec = [ '-c:v', encoder, '-crf', str(crf) ]
    args = [
        'ffmpeg', '-hide_banner', '-y',
        '-i', str(videoPath),
        '-vf', videoFilter,
    ] + videoCodec + [
        #'-c:a', 'copy', '-bsf:a', 'aac_adtstoasc',
        '-map', '0:v', '-map', '0:a', '-ignore_unknown',
        str(outputPath)
    ]
    pipeObj = subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines='\r', errors='ignore')
    info = GetInfoFromLines(pipeObj.stderr)
    duration = info['duration']
    with tqdm(total=duration, unit='secs', disable=quiet) as pbar:
        pbar.set_description('Encoding')
        for line in pipeObj.stderr:
            if 'time=' in line:
                for item in line.split(' '):
                    if item.startswith('time='):
                        timeFields = item.replace('time=', '').split(':')
                        time = float(timeFields[0]) * 3600 + float(timeFields[1]) * 60  + float(timeFields[2])
                        pbar.update(time - pbar.n)
        pbar.update(duration - pbar.n)
    pipeObj.wait()
    shutil.copystat(videoPath, outputPath)
    return outputPath

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Python script to transcode video')
    parser.add_argument('--quiet', '-q', action='store_true', help="don't output to the console")
    subparsers = parser.add_subparsers(required=True, title='subcommands', dest='command')

    subparser = subparsers.add_parser('strip', help='mark CM clips in the mpegts file')
    subparser.add_argument('--input', '-i', required=True, help='input video file name (wildchars supported)')
    subparser.add_argument('--languages', nargs='+', default=[ 'jpn', 'jpn' ], help="audio language names")
    subparser.add_argument('--repack', action='store_true', help="extract all streams and repack")
    subparser.add_argument('--output', '-o', help='output video file name')

    subparser = subparsers.add_parser('encode', help='mark CM clips in the mpegts file')
    subparser.add_argument('--input', '-i', required=True, help='input video file name (wildchars supported)')
    subparser.add_argument('--preset', '-p', required=True, help='preset for the video')
    subparser.add_argument('--cropdetect', '-c', action='store_true', help='detect and crop still area')
    subparser.add_argument('--encoder', default='hevc', help='video encoder name')
    subparser.add_argument('--crf', default=22, help='CRF value for the video encoder')
    subparser.add_argument('--notag', action='store_true', help="don't add tag to output filename")
    subparser.add_argument('--output', '-o', help='output video file name')

    args = parser.parse_args()

    videoPath = Path(args.input)
    for path in videoPath.parent.glob(videoPath.name):
        if args.command == 'strip':
            print(f'Striping {path} ...')
            if args.repack:
                outputPath = StripAndRepackTS(videoPath=path, outputPath=args.output, audioLanguages=args.languages, quiet=args.quiet)
            else:
                outputPath = StripTS(videoPath=path, outputPath=args.output, audioLanguages=args.languages, quiet=args.quiet)
            pass
        elif args.command == 'encode':
            print(f'Encoding {path} ...')
            outputPath = EncodeTS(
                videoPath=path,
                preset=args.preset,
                cropdetect=args.cropdetect,
                encoder=args.encoder,
                crf=args.crf,
                outputPath=args.output,
                notag=args.notag,
                quiet=args.quiet)
        print('Compress rate: {}%'.format(round(outputPath.stat().st_size / path.stat().st_size * 100, 2)))