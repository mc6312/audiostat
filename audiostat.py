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
from collections import namedtuple, OrderedDict
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
DEFAULT_MIN_BITRATE = 192


class BaseAudioInfo(Representable):
    def get_info_strings(self):
        """Возвращает список строк для форматирования
        текста с информацией об объекте."""

        return []

    def get_hint_str(self):
        return '\n'.join(self.get_info_strings())


class AudioStreamInfo(BaseAudioInfo):
    RESOLUTION_LOW, RESOLUTION_STANDARD, RESOLUTION_HIGH = range(3)
    RESOLUTION_MIN = RESOLUTION_LOW
    RESOLUTION_MAX = RESOLUTION_HIGH

    BITRATE_MIN = 8
    BITRATE_MAX = 1000000 #!

    """Информация об аудиопотоке:
    lossy           - булевское; True, если использовано сжатие с потерями;
    resolution      - None или RESOLUTION_*; "разрешение" потока по значениям
                      sampleRate и bitsPerSample;
                      параметры проверки см. в функции get_audio_file_info();
    sampleRate      - целое, частота сэмплирования,
    channels        - целое, кол-во каналов;
    bitsPerSample   - целое, разрядность; м.б. 0 (неизвестно) для MP3 и
                      подобных форматов;
    bitRate         - целое, битрейт в килобитах/сек. (для форматов, где он известен);
    missingTags     - целое, битовые флаги TAG_xxx; ненулевое значение
                      в случае отсутствия важных тэгов в метаданных файла."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.lossy = True
        self.resolution = None
        self.sampleRate = 0
        self.channels = 0
        self.bitsPerSample = 0
        self.bitRate = 0
        self.missingTags = 0

    def get_info_strings(self):
        r = super().get_info_strings()

        mt = missing_tags_to_str(self.missingTags)
        if mt:
            r.append('Missing tags: %s' % mt)

        return r


def missing_tags_to_str(mtflags):
    """Возвращает строку со списком тэгов,
    соответствующих битовым полям mtflags (целого)."""

    mt = []

    for ixtag, tag in enumerate(TAGS):
        if mtflags & (1 << ixtag):
            mt.append(tag[0])

    return  ', '.join(mt)


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

    def get_info_strings(self):
        r = super().get_info_strings()

        if self.error:
            r.append('Error: %s' % self.error)

        return r


class AudioDirectoryInfo(BaseAudioInfo):
    """Класс для сбора статистики по каталогу с аудиофайлами.

    minInfo, maxInfo - экземпляры AudioStreamInfo,
    содержащие соответствующие значения после одного
    или более вызовов метода update_from_file();

    nFiles - целое, количество обработанных файлов."""

    def __init__(self):
        self.nFiles = 0
        self.nErrors = 0
        self.minInfo = AudioStreamInfo()
        self.maxInfo = AudioStreamInfo()

        self.reset()

    def reset(self):
        """Сброс счётчиков"""

        self.nFiles = 0
        self.nErrors = 0

        self.minInfo.reset()
        # в "минимальное" поле кладём максимальные допустимые значения!
        self.minInfo.lossy = False
        self.minInfo.resolution = AudioStreamInfo.RESOLUTION_MAX

        self.minInfo.sampleRate = 100000000
        self.minInfo.channels = 16384
        self.minInfo.bitsPerSample = 1024
        self.minInfo.bitRate = 1000000000

        self.maxInfo.reset()
        self.maxInfo.resolution = AudioStreamInfo.RESOLUTION_MIN

    def flush(self):
        """Сброс неиспользованных счётчиков.
        Метод должен вызываться после завершения обхода каталога."""

        if self.minInfo.sampleRate > self.maxInfo.sampleRate:
            self.minInfo.sampleRate = 0

        if self.minInfo.channels > self.maxInfo.channels:
            self.minInfo.channels = 0

        if self.minInfo.bitsPerSample > self.maxInfo.bitsPerSample:
            self.minInfo.bitsPerSample = 0

        if self.minInfo.bitRate > self.maxInfo.bitRate:
            self.minInfo.bitRate = 0

        if self.minInfo.resolution is not None\
           and self.maxInfo.resolution is not None\
           and self.minInfo.resolution > self.maxInfo.resolution:
            self.minInfo.resolution = None

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

        if nfo.resolution is not None:
            if self.minInfo.resolution < nfo.resolution:
                self.minInfo.resolution = nfo.resolution

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

        if nfo.resolution is not None:
            if self.maxInfo.resolution > nfo.resolution:
                self.maxInfo.resolution = nfo.resolution

    def update_from_dir(self, other):
        """Пополнение статистики из другого экземпляра
        (напр. при рекурсивном обходе каталогов)."""

        self.nFiles += other.nFiles
        self.nErrors += other.nErrors

        self.__update_min(other.minInfo)
        self.__update_max(other.maxInfo)

        self.minInfo.lossy |= other.minInfo.lossy
        self.minInfo.missingTags |= other.minInfo.missingTags

    def update_from_file(self, nfo):
        """Пополнение статистики.
        nfo - экземпляр AudioFileInfo."""

        self.nFiles += 1

        if nfo.error:
            self.nErrors += 1
        else:
            self.__update_min(nfo)
            self.__update_max(nfo)

            self.minInfo.lossy |= nfo.lossy

            self.minInfo.missingTags |= nfo.missingTags

    def get_info_strings(self):
        r = super().get_info_strings()

        mt = missing_tags_to_str(self.minInfo.missingTags)
        if mt:
            r.append('Missing tags: %s' % mt)

        if self.nErrors:
            r.append('Invalid files: %d' % self.nErrors)

        return r


class AudioFileFilter(Representable):
    """Параметры фильтрации аудиофайлов.

    Поля:
        byFileTypes:
            булевское, True - фильтровать по типам (расширениям) файлов;
        fileTypes:
            множество строк - типов (расширений) файлов;
            по умолчанию - DEFAULT_AUDIO_FILE_EXTS;

        byContainsStreamParameters:
            булевское, True - фильтровать по наличию параметров
            аудиопотока в файле;
        onlyContainsStreamParameters:
            булевское, True - учитывать только файлы, содержащие
            параметры аудиопотока;
            этот фильтр предназначен для выявления файлов, не поддерживаемых
            mutagen (т.е. с ненулевой вероятностью - экзотических
            или устаревших форматов);

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
            BitrateLowerThan==False);

        byTags:
            булевское, True - фильтровать по наличию всех важных тэгов
            (перечисленных в списке TAGS);
        onlyWithoutTags:
            булевское, True - показывать только файлы, где нет хотя бы
            одного важного тэга;

        byErrors:
            булевское, True - фильтровать файлы по наличию ошибок
            обработки (разбора mutagen'ом);
        withErrors:
            булевское, True - показывать только файлы с ошибками."""

    __fpar = namedtuple('__fpar', 'defval tostr fromstr')

    # 'name':(default, tostr, fromstr)
    PARAMETERS = OrderedDict({
        'byFileTypes': __fpar(False, str, str_to_bool),
        'fileTypes': __fpar(DEFAULT_AUDIO_FILE_EXTS, set_to_str, set_from_str),
        'byContainsStreamParameters': __fpar(False, str, str_to_bool),
        'onlyContainsStreamParameters': __fpar(False, str, str_to_bool),
        'byMissingTags': __fpar(False, str, str_to_bool),
        'onlyMissingTags': __fpar(True, str, str_to_bool),
        'byLossless': __fpar(False, str, str_to_bool),
        'onlyLossless': __fpar(True, str, str_to_bool),
        'byResolution': __fpar(False, str, str_to_bool),
        'resolution': __fpar(AudioStreamInfo.RESOLUTION_LOW, str,
                            lambda s: str_to_int(s,
                                AudioStreamInfo.RESOLUTION_MIN,
                                AudioStreamInfo.RESOLUTION_MAX)),
        'byBitrate': __fpar(False, str, str_to_bool),
        'bitrateLowerThan': __fpar(True, str, str_to_bool),
        'bitrateLowerThanValue': __fpar(DEFAULT_MIN_BITRATE, str,
                            lambda s: str_to_int(s,
                                AudioStreamInfo.BITRATE_MIN,
                                AudioStreamInfo.BITRATE_MAX)),
        'bitrateGreaterThanValue': __fpar(DEFAULT_MIN_BITRATE, str,
                            lambda s: str_to_int(s,
                                AudioStreamInfo.BITRATE_MIN,
                                AudioStreamInfo.BITRATE_MAX)),
        'byErrors': __fpar(False, str, str_to_bool),
        'onlyWithErrors': __fpar(False, str, str_to_bool),
        })

    def __init__(self):
        for pname, fpar in self.PARAMETERS.items():
            setattr(self, pname, fpar.defval)

    def get_parameter_str(self, pname):
        """Возвращает значение параметра с именем pname, преобразованное
        в строку."""

        # ЗДЕСЬ: если pname неправильное, просто рухнем с исключением
        # проверкой имён занимается класс Config
        fpar = self.PARAMETERS[pname]

        return fpar.tostr(getattr(self, pname))

    def set_parameter_str(self, pname, v):
        """Устанавливает значение параметра с именем "pname",
        преобразовав его в нужный тип из строки."""

        # ЗДЕСЬ: если pname неправильное, просто рухнем с исключением
        # проверкой имён занимается класс Config
        fpar = self.PARAMETERS[pname]

        try:
            setattr(self, pname, fpar.fromstr(v))
        except Exception as ex:
            raise ValueError('%s.set_parameter_str(): invalid value of parameter "%s" (%s)' % (
                self.__class__.__name__, pname, str(ex)))

    def filetypes_from_str(self, fts):
        self.fileTypes = set_from_str(fts.split(None))

    def filetypes_to_str(self):
        return set_to_str(self.fileTypes)

    def file_match_types(self, fname):
        """Проверяет тип файла по расширению, возвращает булевское
        значение (True - если файл нужного типа).

        fname - строка, имя файла."""

        fext = os.path.splitext(fname)[-1].lower()

        # расширение проверяем в любом случае:
        # если указано "проверять тип" - по выбранным типам
        # иначе - по всем известным типам
        return fext in (self.fileTypes if self.byFileTypes else DEFAULT_AUDIO_FILE_EXTS)

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

            if self.byErrors and self.onlyWithErrors:
                # файл без ошибок, а тут мы хотим одних лишь ошибок
                return

            #
            hasParameters = 0

            if f:
                # извлекаем параметры и метаданные,
                # фильтровать по всему этому будем потом

                #
                nfo.mime = str(f.mime[0])
                nfo.lossy = nfo.mime not in LOSSLESS_MIMETYPES

                #
                nfo.sampleRate = __get_info_fld(f.info, 'sample_rate', 0)
                nfo.channels = __get_info_fld(f.info, 'channels', 1)
                nfo.bitsPerSample = __get_info_fld(f.info, 'bits_per_sample', 0)
                nfo.bitRate = int(__get_info_fld(f.info, 'bitrate', 0) / 1024)

                for v in (nfo.sampleRate, nfo.channels, nfo.bitsPerSample, nfo.bitRate):
                    if v > 0:
                        hasParameters += 1

                #
                tags = getattr(f, 'tags', None)
                if tags:
                    nfo.missingTags = 0

                    for ix, (_, tnames) in enumerate(TAGS):
                        if not __has_tags(f, tnames):
                            nfo.missingTags = nfo.missingTags or (1 << ix)
                # для тэгов hasParameters не трогаем, тэги - не параметры аудиопотока

            #
            # теперь уже пытаемся фильтровать
            #

            #
            if self.byContainsStreamParameters:
                if self.onlyContainsStreamParameters:
                    if not hasParameters:
                        return
                else:
                    if hasParameters:
                        return

            #
            if self.byLossless and self.onlyLossless and nfo.lossy:
                return

            #
            # пока проверка "на хайрез" приколочена гвоздями здесь
            #
            # ВНИМАНИЕ! файлы
            if nfo.bitsPerSample < 16 or nfo.sampleRate < 44100:
                nfo.resolution = AudioStreamInfo.RESOLUTION_LOW
            elif nfo.bitsPerSample > 16 and nfo.sampleRate >= 44100:
                nfo.resolution = AudioStreamInfo.RESOLUTION_HIGH
            else:
                nfo.resolution = AudioStreamInfo.RESOLUTION_STANDARD

            if self.byResolution and self.resolution != nfo.resolution:
                return

            #
            if self.byBitrate:
                if self.bitrateLowerThan:
                    if nfo.bitRate > self.bitrateLowerThanValue:
                        return
                elif nfo.bitRate < self.bitrateGreaterThanValue:
                    return

            #

            if self.byMissingTags:
                if (self.onlyMissingTags and nfo.missingTags == 0) or\
                        (not self.onlyMissingTags and nfo.missingTags != 0):
                    return

        except mutagen.MutagenError as ex:
            # с прочими исключениями - обязательно падаем!

            if not self.byErrors:
                return

            nfo.error = str(ex)

        return nfo


class AudioFileList(Representable):
    """Дерево каталогов с аудиофайлами для последующей их обработки.

    Поля:
        files       - экземпляр DirectoryItem;
        totalFiles  - целое, количество всех найденных аудиофайлов."""

    class DirectoryItem():
        __slots__ = 'isdir', 'name', 'children'

        """Элемент каталога ФС.

        Поля:
        isdir       - булевское значение, True для каталога, False для файла;
        name        - имя файла или каталога (только имя, не полный путь);
        children    - список файлов и подкаталогов, если isdir==True,
                      иначе None."""

        def __init__(self, name, isdir):
            self.name = name
            self.isdir = isdir
            self.children = [] if isdir else None

    def __init__(self, fromDir, fileFilter, progress):
        """Рекурсивный поиск файлов в указанном каталоге, сохранение имён
        найденных файлов в дереве files (экземпляре AudioFileList).

        Параметры:
            fromDir     - строка, путь к каталогу, в котором следует
                          искать файлы;
            fileFilter  - экземпляр AudioFileFilter;
            progress    - None или функция отображения прогресса;
                          функция получает на входе два параметра:
                          1й: строка с путём к текущему каталогу;
                          2й: количество найденных файлов;
                          функция должна возвращать булевское значение:
                          True для продолжения поиска файлов,
                          False для прекращения.

        Поиск производится рекурсивно."""

        if not callable(progress):
            progress = None

        self.files = self.DirectoryItem('', True)

        self.totalFiles = 0

        def __scan_dir(dest, path):
            """Рекурсивный обход каталога.

            dest    - экземпляр DirectoryItem, куда следует складывать
                      имена файлов и подкаталогов;
            path    - полный путь к каталогу.

            Возвращает булевское значение - True для продолжения
            поиска файлов, False для прекращения."""

            if progress and not progress(path, self.totalFiles):
                return False

            for fname in os.listdir(path):
                fpath = os.path.join(path, fname)

                if os.path.isdir(fpath):
                    subdir = self.DirectoryItem(fname, True)
                    if not __scan_dir(subdir, fpath):
                        return False

                    if subdir.children:
                        dest.children.append(subdir)
                else:
                    if fileFilter.file_match_types(fname):
                        dest.children.append(self.DirectoryItem(fname, False))
                        self.totalFiles += 1

            return True

        __scan_dir(self.files, fromDir)


def __test_scan_directory(cfg):
    def __scan_progress(fpath, nFiles):
        print('\033[1mscanning: %s/\033[0m' % fpath)
        return True

    tree = AudioFileList(cfg.lastDirectory, cfg.filter, __scan_progress)

    print(tree)

    def __process_diritem(diritem, parent):
        if diritem.isdir:
            fpath = os.path.join(parent, diritem.name)
            print('\033[1m%s\033[0m' % fpath)

            for i in diritem.children:
                __process_diritem(i, fpath)
        else:
            print(diritem.name)

    __process_diritem(tree.files, '')


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    import asconfig

    cfg = asconfig.Config()
    cfg.load()
    #print(cfg)
    __test_scan_directory(cfg)
