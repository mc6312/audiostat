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
VERSION = '1.1'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)


import sys
import os
import os.path
import mutagen
from collections import namedtuple
from traceback import print_exception


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


def disp_int_val_k(i):
    return '?' if not i else '%.1f' % (i / 1000.0)


def disp_int_val(i):
    return '?' if not i else str(i)


def disp_int_range(a, b):
    if a == b:
        return disp_int_val(a)
    else:
        return '%s…%s' % (disp_int_val(a), disp_int_val(b))


def disp_int_range_k(a, b):
    if a == b:
        return disp_int_val_k(a)
    else:
        return '%s - %s' % (disp_int_val_k(a), disp_int_val_k(b))


def disp_bool(b, vtrue):
    return None if not b else vtrue


class __ReprBase():
    """Класс-костыль для упрощения написания метода __repr__()
    в классах с наследованием.
    repr(obj) для экземпляра такого класса возвращает
    "прилизанную" строку, содержащую отображения только нужных,
    т.е. явно указанных в методе __repr_fields__() полей."""

    def __repr_fields__(self):
        """Костыль для наследования __repr__.
        Должен возвращать список, содержащий кортежи из двух
        элементов - названия поля и значения, при необходимости
        преобразованного в строку в виде, пригодном для __repr__;
        цельночисленные, булевские и т.п. значения следует
        возвращать "как есть"."""

        return []

    def __repr__(self):
        """Метод, """
        def __rfld(name, value):
            if isinstance(value, str):
                s = '"%s"' % value
            elif isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
                s = str(value)
            else:
                s = repr(value)

            return '%s=%s' % (name, s)

        return '%s(%s)' % (self.__class__.__name__,
            ', '.join(map(lambda f: __rfld(*f), self.__repr_fields__())))


class AudioStreamInfo(__ReprBase):
    """Информация об аудиопотоке:
    lossy           - булевское; True, если использовано сжатие с потерями;
    lowRes          - булевское; True, если поток не тянет по параметрам
                      на крутой аудиофильский хайрез;
                      параметры проверки см. в функции get_audio_file_info();
    sampleRate      - целое, частота сэмплирования,
    channels        - целое, кол-во каналов;
    bitsPerSample   - целое, разрядность; м.б. 0 (неизвестно) для MP3 и
                      подобных форматов;
    bitRate         - целое, битрейт (для форматов, где он известен);
    missingTags     - целое, битовые флаги TAG_xxx; ненулевое значение
                      в случае отсутствия важных тэгов в метаданных файла."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.lossy = True
        self.lowRes = True
        self.sampleRate = 0
        self.channels = 0
        self.bitsPerSample = 0
        self.bitRate = 0
        self.missingTags = 0

    def __repr_fields__(self):
        return [('lossy', self.lossy),
                ('lowRes', self.lowRes),
                ('sampleRate', self.sampleRate),
                ('channels', self.channels),
                ('bitsPerSample', self.bitsPerSample),
                ('bitRate', self.bitRate),
                ('missingTags', hex(self.missingTags))]


class AudioFileInfo(AudioStreamInfo):
    """Информация об аудиофайле:
    isAudio         - булевское значение, False, если файл не является
                      аудиофайлом известного формата; в этом случае все
                      прочие поля должны игнорироваться;
    error           - строка:
                      при отсутствии ошибок: пустая строка или None,
                      иначе - сообщение об ошибке; в последнем случае
                      все последующие поля должны игнорироваться;
    mime            - строка, mimetype;

    Прочие поля наследуются от AudioStreamInfo."""

    def __init__(self):
        super().__init__()

        self.isAudio = False
        self.error = None
        self.mime = ''

    def __repr_fields__(self):
        return super().__repr_fields__() + [
            ('isAudio', self.isAudio),
            ('error', 'None' if self.error is None else '"%s"' % self.error),
            ('mime', self.mime)]


class AudioDirectoryInfo(__ReprBase):
    """Класс для сбора статистики по каталогу с аудиофайлами.

    minInfo, maxInfo - экземпляры AudioStreamInfo,
    содержащие соответствующие значения после одного
    или более вызовов метода update_from_file();

    nFiles - целое, количество обработанных файлов."""

    def __init__(self):
        self.nFiles = 0
        self.minInfo = AudioStreamInfo()
        self.maxInfo = AudioStreamInfo()

        self.reset()

    def reset(self):
        """Сброс счётчиков"""

        self.nFiles = 0

        self.minInfo.reset()
        # в "минимальное" поле кладём максимальные допустимые значения!
        self.minInfo.lossy = False
        self.minInfo.lowRes = False

        self.minInfo.sampleRate = 100000000
        self.minInfo.channels = 16384
        self.minInfo.bitsPerSample = 1024
        self.minInfo.bitRate = 1000000000

        self.maxInfo.reset()

    def __update_min(self, nfo):
        """Пополнение "минимальных" счётчиков из экземпляра
        AudioStreamInfo."""

        if self.minInfo.sampleRate > nfo.sampleRate:
            self.minInfo.sampleRate = nfo.sampleRate

        if self.minInfo.channels > nfo.channels:
            self.minInfo.channels = nfo.channels

        if self.minInfo.bitsPerSample > nfo.bitsPerSample:
            self.minInfo.bitsPerSample = nfo.bitsPerSample

        if self.minInfo.bitRate > nfo.bitRate:
            self.minInfo.bitRate = nfo.bitRate

    def __update_max(self, nfo):
        """Пополнение "максимальных" счётчиков из экземпляра
        AudioStreamInfo."""

        if self.maxInfo.sampleRate < nfo.sampleRate:
            self.maxInfo.sampleRate = nfo.sampleRate

        if self.maxInfo.channels < nfo.channels:
            self.maxInfo.channels = nfo.channels

        if self.maxInfo.bitsPerSample < nfo.bitsPerSample:
            self.maxInfo.bitsPerSample = nfo.bitsPerSample

        if self.maxInfo.bitRate < nfo.bitRate:
            self.maxInfo.bitRate = nfo.bitRate

    def update_from_dir(self, other):
        """Пополнение статистики из другого экземпляра
        (напр. при рекурсивном обходе каталогов)."""

        self.nFiles += 1

        self.__update_min(other.minInfo)
        self.__update_max(other.maxInfo)

        self.minInfo.lossy |= other.minInfo.lossy
        self.minInfo.lowRes |= other.minInfo.lowRes
        self.minInfo.missingTags |= other.minInfo.missingTags

    def update_from_file(self, nfo):
        """Пополнение статистики.
        nfo - экземпляр AudioFileInfo."""

        self.nFiles += 1

        self.__update_min(nfo)
        self.__update_max(nfo)

        self.minInfo.lossy |= nfo.lossy
        self.minInfo.lowRes |= nfo.lowRes
        self.minInfo.missingTags |= nfo.missingTags


def get_audio_file_info(fpath, ftypes=AUDIO_FILE_TYPES):
    """Извлечение параметров потока и метаданных из аудиофайла.
    Возвращает экземпляр AudioFileInfo."""

    def __get_info_fld(info, name, fallback):
        if name in info.__dict__:
            return getattr(info, name)
        else:
            return fallback

    nfo = AudioFileInfo()
    if not os.path.splitext(fpath)[-1].lower() in ftypes:
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

        # пока проверка "на хайрез" минимальная
        nfo.lowRes = (nfo.bitsPerSample < 24) and (nfo.sampleRate < 88200)

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

    import asconfig

    cfg = asconfig.Config()
    __test_scan_directory(cfg.lastDirectory)
