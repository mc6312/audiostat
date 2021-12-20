#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" audiostat.py

    Copyright 2021 MC-6312

    his file is part of AudioStat.

    AudioStat is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    AudioStat is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with AudioStat.  If not, see <http://www.gnu.org/licenses/>."""


TITLE = 'AudioStat'
VERSION = '0.1'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)


import sys
import os
import os.path
import mutagen
from collections import namedtuple
from traceback import print_exception


audiotype = namedtuple('audiotype', 'name lossy')
"""name - строка, человекочитаемое название типа;
lossy   - булевское, True для аудиоформатов, сжимающих с потерями."""

AUDIO_FILE_TYPES = {'.wav', '.mp3', '.flac', '.ape', '.mpa', '.ogg',
    '.wv', '.ac3', '.aac', '.mka', '.dts', '.webm'}

#TODO пополнить LOSSLESS_MIMETYPES при необходимости
LOSSLESS_MIMETYPES = {'audio/flac', 'audio/x-ape', 'audio/x-wavpack'}


TAGS = (('title', ('TITLE', 'TIT2')),
        ('artist', ('ARTIST', 'TPE1')),
        ('album artist', ('ALBUMARTIST', 'TPE2')),
        ('album', ('ALBUM', 'TALB')),
        ('track number', ('TRACKNUMBER', 'TRCK')),
        ('genre', ('TCON', 'GENRE')),
        ('year', ('DATE', 'TDRC')),
        )


class AudioFileInfo():
    __slots__ = 'isAudio', 'error', 'lossy', 'mime', 'sampleRate', 'channels', 'bitsPerSample', 'bitRate', 'missingTags'

    """Информация об аудиофайле:
    isAudio         - булевское значение, False, если файл не является
                      аудиофайлом известного формата; в этом случае все
                      прочие поля должны игнорироваться;
    error           - строка:
                      при отсутствии ошибок: пустая строка или None,
                      иначе - сообщение об ошибке; в последнем случае
                      все последующие поля должны игнорироваться;
    lossy           - булевское; True, если в файле использовано сжатие
                      с потерями;
    mime            - строка, mimetype;
    sampleRate      - целое, частота сэмплирования,
    channels        - целое, кол-во каналов;
    bitsPerSample   - целое, разрядность; м.б. 0 (неизвестно) для MP3 и
                      подобных форматов;
    bitRate         - целое, битрейт (для форматов, где он известен);
    missingTags     - целое, битовые флаги TAG_xxx; ненулевое значение
                      в случае отсутствия важных тэгов в метаданных файла."""

    def __init__(self):
        self.isAudio = False
        self.error = None
        self.lossy = True
        self.mime = ''
        self.sampleRate = 0
        self.channels = 0
        self.bitsPerSample = 0
        self.bitRate = 0
        self.missingTags = -1 # ваще нет тэгов

    def __repr__(self):
        if self.missingTags < 0:
            mt = ['all']
        else:
            mt = []

            for ix, (tname, _) in enumerate(TAGS):
                if self.missingTags & (1 << ix):
                    mt.append(tname)

        return '%s(isAudio=%s, error=%s, lossy=%s, mime="%s", sampleRate=%d, channels=%d, bitsPerSample=%d, bitRate=%d, missingTags=<%s>)' % (self.__class__.__name__,
            self.isAudio,
            'None' if self.error is None else '"%s"' % self.error,
            self.lossy,
            self.mime,
            self.sampleRate, self.channels, self.bitsPerSample, self.bitRate,
            ', '.join(mt))


def get_audio_file_info(fpath):
    """Извлечение параметров потока и метаданных из аудиофайла.
    Возвращает экземпляр AudioFileInfo."""

    def __get_info_fld(info, name, fallback):
        if name in info.__dict__:
            return getattr(info, name)
        else:
            return fallback

    nfo = AudioFileInfo()
    if not os.path.splitext(fpath)[-1].lower() in AUDIO_FILE_TYPES:
        return nfo

    nfo.isAudio = True

    def __has_tags(fnfo, tnames):
        for n in tnames:
            if n in fnfo:
                return True

        return False

    try:
        f = mutagen.File(fpath)

        if not f:
            return nfo

        nfo.mime = str(f.mime[0])

        nfo.lossy = nfo.mime not in LOSSLESS_MIMETYPES

        tags = getattr(f, 'tags', None)
        if tags:
            nfo.missingTags = 0

            for ix, (_, tnames) in enumerate(TAGS):
                if not __has_tags(f, tnames):
                    nfo.missingTags = nfo.missingTags or (1 << ix)

        nfo.sampleRate = __get_info_fld(f.info, 'sample_rate', 0)
        nfo.channels = __get_info_fld(f.info, 'channels', 1)
        nfo.bitsPerSample = __get_info_fld(f.info, 'bits_per_sample', 0)
        nfo.bitRate = __get_info_fld(f.info, 'bitrate', 0)

    except Exception as ex:
        print_exception(*sys.exc_info())
        nfo.error = repr(ex)

    return nfo


def __test_scan_directory(path):
    print('\033[1m%s/\033[0m' % path)

    for fname in os.listdir(path):
        fpath = os.path.join(path, fname)

        if os.path.isdir(fpath):
            __test_scan_directory(fpath)
        else:
            print('\033[32m%s\033[0m' % fname)
            r = get_audio_file_info(fpath)
            print(r)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    __test_scan_directory(os.path.expanduser('~/docs-private/misc'))
