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


from ascommon import *


import sys
import os
import os.path
import mutagen
from collections import namedtuple
from enum import IntEnum
from traceback import print_exception


__aft = namedtuple('__aft', 'name exts')

AUDIO_FILE_TYPES = (
    __aft('FLAC',            {'.flac'}),
    __aft('WavPack',         {'.wv'}),
    __aft('Monkey’s Audio',  {'.ape'}),
    __aft('MPEG Layer 3',    {'.mp3'}),
    __aft('MPEG4 Audio',     {'.m4a'}),
    __aft('OGG Vorbis',      {'.ogg', '.oga'}),
    __aft('OGG Opus',        {'.opus'}),
    __aft('OptimFROG',       {'.ofr'}),
    __aft('AIFF',            {'.aif', '.aiff', '.aifc'}),
    __aft('Wave',            {'.wav'}),
    # форматы, (в том числе) не поддерживаемые mutagen,
    # но могущие оказаться в аудиотеке
    __aft('Other formats',   {'.webm'}),
    )


DEFAULT_AUDIO_FILE_EXTS = set()

for __, __exts in AUDIO_FILE_TYPES:
    DEFAULT_AUDIO_FILE_EXTS.update(__exts)


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


# значение порога для фильтрации
DEFAULTT_MIN_BITRATE = 192


class AudioFileFilter(Representable):
    """Параметры фильтрации аудиофайлов.

    Поля:
        byFileTypes:
            булевское, True - фильтровать по типам (расширениям) файлов;
        fileTypes:
            множество строк - типов (расширений) файлов;
            по умолчанию - DEFAULT_AUDIO_FILE_EXTS;

        byLossless:
            булевское, True - фильтровать по формату сжатия (без потерь/
            с потерями);
        onlyLossless:
            булевское, True - учитывать только аудио, сжатое без потерь;

        byResolution:
            булевское, True - фильтровать по разрешению;
        resolution:
            AudioStream.Resolution;

        byBitrate:
            булевское, True - фильтровать по битрейту;
        bitrateLowerThan:
            булевское, True - учитывать аудио с битрейтом ниже указанного
            значения;
        bitrateLowerThanValue:
            целое, максимальное значение битрейта (используется, если
            BitrateLowerThan==True);
        bitrateGreaterThanValue:
            целое, минимальное значение битрейта (используется, если
            BitrateLowerThan==False)."""

    def __init__(self):
        self.byFileTypes = False
        self.fileTypes = DEFAULT_AUDIO_FILE_EXTS

        self.byLossless = False
        self.onlyLossless = True

        self.byResolution = False
        self.resolution = AudioStreamInfo.RESOLUTION_LOW

        self.byBitrate = False
        self.bitrateLowerThan = True
        self.bitrateLowerThanValue = DEFAULTT_MIN_BITRATE
        self.bitrateGreaterThanValue = DEFAULTT_MIN_BITRATE

    def has_data_filters(self):
        """Возвращает True, если заданы хоть какие-нибудь
        параметры фильтрации."""

        return self.byLossless or self.byResolution or self.byBitrate

    def filetypes_from_str(self, fts):
        self.fileTypes = set(map(lambda s: s.lower(), fts.split(None)))

    def filetypes_to_str(self):
        return ' '.join(sorted(self.fileTypes))

    def get_audio_file_info(self, fpath):
        """Проверка типа файла и извлечение параметров потока
        и метаданных из аудиофайла.

        Параметры:
            fpath   - строка, полный путь к файлу;
            fexts   - множество строк - расширений (типов) файлов.

        Возвращает экземпляр AudioFileInfo, если файл - поддерживаемого
        типа и соответствует параметрам фильтрации,
        в прочих случаях - None."""

        def __get_info_fld(info, name, fallback):
            if name in info.__dict__:
                return getattr(info, name)
            else:
                return fallback

        if not os.path.splitext(fpath)[-1].lower() in self.fileTypes:
            return

        nfo = AudioFileInfo()

        def __has_tags(fnfo, tnames):
            for n in tnames:
                if n in fnfo:
                    return True

            return False

        try:
            f = mutagen.File(fpath)

            #
            # фильтрация по указанным параметрам.
            # файлы, не прошедшие фильтрацию - отбрасываем
            #

            if not f:
                if self.has_data_filters():
                    # метаданных в файле нет, но фильтр хочет метаданных
                    # потому файл отбрасываем
                    return

                # файл известного типа, но без метаданных
                # честно возвращаем инфу с пустыми полями...
                return nfo

            #
            nfo.mime = str(f.mime[0])
            nfo.lossy = nfo.mime not in LOSSLESS_MIMETYPES

            if self.byLossless:
                if self.onlyLossless and nfo.lossy:
                    return

            nfo.sampleRate = __get_info_fld(f.info, 'sample_rate', 0)
            nfo.channels = __get_info_fld(f.info, 'channels', 1)
            nfo.bitsPerSample = __get_info_fld(f.info, 'bits_per_sample', 0)
            nfo.bitRate = __get_info_fld(f.info, 'bitrate', 0)

            #
            # пока проверка "на хайрез" приколочена гвоздями здесь
            # потом
            if nfo.bitsPerSample < 16 or nfo.sampleRate < 44100:
                nfo.resolution = AudioStreamInfo.RESOLUTION_LOW
            elif nfo.bitsPerSample > 16 and nfo.sampleRate >= 44100:
                nfo.resolution = AudioStreamInfo.RESOLUTION_HIGH
            else:
                nfo.resolution = AudioStreamInfo.RESOLUTION_STANDARD

            if self.byResolution:
                if self.resolution and nfo.resolution:
                    return

            #
            if self.byBitrate:
                if self.bitrateLowerThan:
                    if nfo.bitRate > self.bitrateLowerThanValue:
                        return
                elif nfo.bitRate < self.bitrateGreaterThanValue:
                    return

            tags = getattr(f, 'tags', None)
            if tags:
                nfo.missingTags = 0

                for ix, (_, tnames) in enumerate(TAGS):
                    if not __has_tags(f, tnames):
                        nfo.missingTags = nfo.missingTags or (1 << ix)

        except mutagen.MutagenError as ex:
            # с прочими исключениями - обязательно падаем!
            #TODO прикрутить фильтрацию для файлов с ошибками чтения и/или метаданных
            #print_exception(*sys.exc_info())
            nfo.error = str(ex)

        return nfo



class AudioStreamInfo(Representable):
    RESOLUTION_LOW, RESOLUTION_STANDARD, RESOLUTION_HIGH = range(3)
    RESOLUTION_MIN = RESOLUTION_LOW
    RESOLUTION_MAX = RESOLUTION_HIGH

    BITRATE_MIN = 8
    BITRATE_MAX = 1000000 #!

    """Информация об аудиопотоке:
    lossy           - булевское; True, если использовано сжатие с потерями;
    resolution      - RESOLUTION_*; "разрешение" потока по значениям
                      sampleRate и bitsPerSample;
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
        self.resolution = self.RESOLUTION_LOW
        self.sampleRate = 0
        self.channels = 0
        self.bitsPerSample = 0
        self.bitRate = 0
        self.missingTags = 0


class AudioFileInfo(AudioStreamInfo):
    """Информация об аудиофайле.

    Поля:
        error   - None или строка с сообщением об ошибке,
                  если произошла ошибка разбора метаданных;
                  в этом случае все прочие поля должны
                  игнорироваться;
        mime    - строка, mimetype;

    Прочие поля наследуются от AudioStreamInfo."""

    def __init__(self):
        super().__init__()

        self.error = None
        self.mime = ''


class AudioDirectoryInfo(Representable):
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
        self.minInfo.resolution = False

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
        self.minInfo.resolution |= other.minInfo.resolution
        self.minInfo.missingTags |= other.minInfo.missingTags

    def update_from_file(self, nfo):
        """Пополнение статистики.
        nfo - экземпляр AudioFileInfo."""

        self.nFiles += 1

        self.__update_min(nfo)
        self.__update_max(nfo)

        self.minInfo.lossy |= nfo.lossy
        self.minInfo.resolution |= nfo.resolution
        self.minInfo.missingTags |= nfo.missingTags


def __test_scan_directory(path, cfg):
    print('\033[1m%s/\033[0m' % path)

    for fname in os.listdir(path):
        fpath = os.path.join(path, fname)

        if os.path.isdir(fpath):
            __test_scan_directory(fpath, cfg)
        else:
            print('\033[32m%s\033[0m' % fname)
            nfo = cfg.filter.get_audio_file_info(fpath)
            if nfo:
                if not nfo.error:
                    print(nfo)
                else:
                    print('\033[31m*** Error: %s\033[0m' % nfo.error)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    import asconfig

    cfg = asconfig.Config()
    __test_scan_directory(cfg.lastDirectory, cfg)
