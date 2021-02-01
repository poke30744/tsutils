import sys, tempfile, argparse
from pathlib import Path
from pydub import AudioSegment
from pydub.silence import detect_silence
from .ffmpeg import ExtractStream
from .common import FormatTimestamp

def DetectSilence(path, ss=0, to=999999, min_silence_len=800, silence_thresh=-80, quiet=False):
    with tempfile.TemporaryDirectory(prefix='logoNet_wav_') as tmpLogoFolder:
        streamsFolder = ExtractStream(path=path, output=tmpLogoFolder, ss=ss, to=to, toWav=True, quiet=quiet)
        audioFilename = streamsFolder / 'audio_0.wav'
        if not quiet:
            print('Detect silence ...', file=sys.stderr)
        sound = AudioSegment.from_wav(audioFilename).set_channels(1)
        periods = detect_silence(audio_segment=sound, min_silence_len=min_silence_len, silence_thresh=silence_thresh, seek_step=10)
        if not quiet:
            print('done!', file=sys.stderr)
        return periods

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Detect silent periods in TS files')
    parser.add_argument('--quiet', '-q', action='store_true', help="don't output to the console")
    parser.add_argument('--input', '-i', required=True, help='input mpegts path')
    parser.add_argument('--length', '-l', type=int, default=800, help='min silence length in ms')
    parser.add_argument('--threshold', '-t', type=int, default=-80, help='silence threshold')
    args = parser.parse_args()

    silencePeriods = DetectSilence(path=args.input, min_silence_len=args.length, silence_thresh=args.threshold)
    for period in silencePeriods:
        print(FormatTimestamp(period[0] / 1000), period[1] - period[0])