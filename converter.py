# -*- coding: utf-8 -*-

import sys
import os
import hashlib
import logging
import subprocess
import shutil
import time

from unidecode import unidecode
from timeit import default_timer as timer
from pymediainfo import MediaInfo

settings = {
    'tmp_folder': "/tmp/",
    'keep_original': False,
    'original_archive_folder': "/media/converted-sources/",
    'output_file': 'report.txt',
    'logging_level': logging.WARNING,
    'conversion_speed': "veryfast",
    'video_quality': 21,
    'h264_level': "4.0",
    'audio_quality': 6,
    # 'custom_ffmpeg_args': '-af "volume=5dB"',
    'test': False,
    'file_types': (".asf",".asx",'avi','divx',".flv",'m2ts','m4v','mkv','mov','mp4','mpeg','mpg',".vob",'wmv')
}

logging.basicConfig(filename=settings['output_file'], level=settings['logging_level'], format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

def decode_unicode(text):
    return unidecode(unicode(text, encoding="utf-8"))


logging.info("Starting Batch Conversion")

if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    media_directory = sys.argv[1]
else:
    logging.debug("Directory not specified")
    sys.exit(0)

logging.info("Scanning %s", media_directory)

for path, subdirs, files in os.walk(media_directory):
    for name in files:
        do_convert = False
        if name.endswith(settings['file_types']):
            filename = os.path.splitext(name)[0]
            extension = os.path.splitext(name)[1]

            # FFMPEG requires non-unicode characters
            decoded_name = decode_unicode(name)
            decoded_path = decode_unicode(path)
            if path != decoded_path or name != decoded_name:
                logging.info('Unicode in filename: %s | %s', os.path.join(path, name), os.path.join(decoded_path, decoded_name))
                if not os.path.join(decoded_path):
                    os.makedirs(os.path.join(decoded_path))
                shutil.move(os.path.join(path, name), os.path.join(decoded_path, decoded_name))
                # os.rename(os.path.join(path, name), os.path.join(decoded_path, decoded_name))


            logging.debug('Working on %s', decoded_name)
            mi = MediaInfo.parse(os.path.join(decoded_path, decoded_name))
            containers = {
                'General': None,
                'Audio': [],
                'Video': None
            }
            for track in mi.tracks:
                if track.kind_of_stream in containers:
                    if track.kind_of_stream == 'Audio':
                        containers[track.kind_of_stream].append(track.format)
                    else:
                        containers[track.kind_of_stream] = track.format

            if containers['General'] != 'MPEG-4':
                logging.info('ISSUE: Container is not MPEG4 (%s)', containers['General'] )
                do_convert = True

            if containers['Video'] != 'AVC':
                logging.info('ISSUE: Video codec is not AVC/H.264 (%s)',containers['Video'])
                do_convert = True

            if len(containers['Audio']) and containers['Audio'][0] != 'AAC':
                logging.info('ISSUE: Audio codec is not AAC (%s)', containers['Audio'][0])
                do_convert = True

            if len(containers['Audio']) != 1:
                logging.error('ERROR: More than one audio track %s', os.path.join(decoded_path, decoded_name))
                do_convert = False
                continue

            if do_convert:
                hashvalue = hashlib.md5(os.path.join(decoded_path, decoded_name)).hexdigest()
                working_file = os.path.join(settings['tmp_folder'], str(hashvalue) + '.mp4')
                destination_file = os.path.join(path, filename + '.mp4')
                if os.path.isfile(working_file):
                    use_by = time.time() - 2 * 60
                    if os.path.getatime(working_file) < use_by:
                        logging.debug('Conversion in process %s', os.path.join(path, name))
                        continue
                    else:
                        logging.debug('Conversion in process %s', os.path.join(path, name))
                        os.remove(working_file)

                logging.debug('Source: %s', os.path.join(decoded_path, decoded_name))
                logging.debug('Temp: %s', working_file)
                logging.debug('Dest: %s', destination_file)
                start = timer()

                ffmpeg_cmd = 'ffmpeg -i "' + str(os.path.join(decoded_path, decoded_name)) + '" -c:v libx264 -crf ' + str(settings['video_quality'])

                if 'h264_level' in settings and settings['h264_level']:
                    ffmpeg_cmd = ffmpeg_cmd + ' -level ' + str(settings['h264_level'])

                if 'custom_ffmpeg_args' in settings and settings['custom_ffmpeg_args']:
                    ffmpeg_cmd = ffmpeg_cmd + ' ' + str(settings['custom_ffmpeg_args'])

                ffmpeg_cmd = ffmpeg_cmd + ' -preset ' + str(settings['conversion_speed']) + ' -c:a aac -q:a ' + str(settings['audio_quality']) + ' -c:s mov_text -movflags +faststart -strict -2 "' + str(working_file) + '"'

                logging.debug('Running Command: %s', ffmpeg_cmd)
                if not settings['test']:
                    if not os.path.join(settings['tmp_folder']):
                        os.makedirs(os.path.join(settings['tmp_folder']))
                    subprocess.call(ffmpeg_cmd, shell=True)

                # Sometimes ffmpeg creates 0 byte files
                if os.stat(working_file).st_size == 0:
                    logging.error('0 Byte File: %s', os.path.join(decoded_path, decoded_name))
                    continue
                else:
                    if 'keep_original' in settings and settings['keep_original']:
                        logging.debug('Keeping original: %s', os.path.join(settings['original_archive_folder'], name))
                        if not settings['test']:
                            if not os.path.join(settings['original_archive_folder']):
                                os.makedirs(os.path.join(settings['original_archive_folder']))

                            if os.path.isfile(os.path.join(path, name)):
                                shutil.move(os.path.join(path, name), os.path.join(settings['original_archive_folder'], name))
                                # os.rename(os.path.join(path, name), os.path.join(settings['original_archive_folder'], name))
                            if os.path.isfile(os.path.join(decoded_path, decoded_name)):
                                shutil.move(os.path.join(decoded_path, decoded_name), os.path.join(settings['original_archive_folder'], name))
                                # os.rename(os.path.join(decoded_path, decoded_name), os.path.join(settings['original_archive_folder'], name))
                    else:
                        logging.debug('Deleting original: %s', os.path.join(path, name))
                        if not settings['test']:
                            if os.path.isfile(os.path.join(path, name)):
                                os.remove(os.path.join(path, name))
                            if os.path.isfile(os.path.join(decoded_path, decoded_name)):
                                os.remove(os.path.join(decoded_path, decoded_name))

                    logging.info('Moving converted file into place of original...')
                    if not settings['test']:
                        shutil.copyfile(working_file, destination_file)
                        os.remove(working_file)
                        # os.rename(working_file, destination_file)
                        # TODO: Notify plexserver https://support.plex.tv/articles/201638786-plex-media-server-url-commands/

                end = timer()
                time_taken = (end - start)
                logging.info('Conversion finished %s: %s', time_taken, destination_file)
            else:
                logging.info('Not converting this file')

logging.info('Run Complete')
