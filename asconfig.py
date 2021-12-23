#!/usr/bin/env python3
# -*- coding: utf-8 -*-


""" asconfig.py

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


import sys
import os.path
from configparser import ConfigParser

from audiostat import *
from ascommon import *


class Config(Representable):
    """Настройки AudioStat.

    Поля:
        lastDirectory:
            строка, путь к последнему просканированному каталогу;

        filterParams:
            экземпляр класса FilterParams."""

    __S_SETTINGS = 'settings'
    __V_LASTDIR = 'last-directory'

    __S_FILTERS = 'filters'
    __V_FILTER_BY_FILETYPES = 'filter-by-file-types'
    __V_FILTER_FILETYPES = 'file-types'
    __V_FILTER_BY_LOSSLESS = 'filter-by-lossless'
    __V_FILTER_ONLY_LOSSLESS = 'filter-only-lossless'
    __V_FILTER_BY_RESOLUTION = 'filter-by-hi-res'
    __V_FILTER_RESOLUTION = 'filter-resolution'
    __V_FILTER_BY_BITRATE = 'filter-by-bitrate'
    __V_FILTER_BITRATE_LOWER = 'filter-bitrate-lower-than'
    __V_FILTER_BITRATE_LOWER_VALUE = 'filter-bitrate-lower-value'
    __V_FILTER_BITRATE_GREATER_VALUE = 'filter-bitrate-greater-value'

    def __init__(self):
        #
        # ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ
        #

        #
        # основные настройки
        #
        self.lastDirectory = os.path.expanduser('~')

        #
        # параметры фильтрации
        #
        self.filter = AudioFileFilter()

        #
        # подготовка к загрузке
        #

        #
        if sys.platform == 'linux':
            # ...а если дистрибутив не XDG-совместимый, то это не моя проблема
            self.pathConfig = os.path.expanduser('~/.config/audiostat.cfg')
        elif sys.platform == 'win32':
            # для винды и так сойдёт
            self.pathConfig = os.path.join(os.environ['USERPROFILE'], 'audiostat.cfg')
        else:
            # тут предполагаем что-то *nix-образное, пусть даже и макось
            self.pathConfig = os.path.expanduser('~/.audiostat.cfg')

        # пытаемся загрузить конфиг
        cfg = ConfigParser()

        if not os.path.exists(self.pathConfig):
            return

        cfg.read(self.pathConfig)

        #
        # тащим значения из конфига в поля сего объекта
        #
        self.lastDirectory = os.path.expanduser(cfg.get(self.__S_SETTINGS,
            self.__V_LASTDIR, fallback=self.lastDirectory))

        #
        self.filter.byFileTypes = cfg.getboolean(self.__S_FILTERS,
            self.__V_FILTER_BY_FILETYPES, fallback=self.filter.byFileTypes)
        self.filter.filetypes_from_str(cfg.get(self.__S_FILTERS,
            self.__V_FILTER_FILETYPES, fallback=self.filter.filetypes_to_str()))

        #
        self.filter.byLossless = cfg.getboolean(self.__S_FILTERS,
            self.__V_FILTER_BY_LOSSLESS, fallback=self.filter.byLossless)
        self.filter.onlyLossless = cfg.getboolean(self.__S_FILTERS,
            self.__V_FILTER_ONLY_LOSSLESS, fallback=self.filter.onlyLossless)

        #
        self.filter.byResolution = cfg.getboolean(self.__S_FILTERS,
            self.__V_FILTER_BY_RESOLUTION, fallback=self.filter.byResolution)
        self.filter.resolution = floor_ceil_int(cfg.getint(self.__S_FILTERS,
            self.__V_FILTER_RESOLUTION, fallback=self.filter.resolution),
            AudioStreamInfo.RESOLUTION_MIN, AudioStreamInfo.RESOLUTION_MAX)

        #
        self.filter.byBitrate = cfg.getboolean(self.__S_FILTERS,
            self.__V_FILTER_BY_BITRATE, fallback=self.filter.byBitrate)
        self.filter.bitrateLowerThan = cfg.getboolean(self.__S_FILTERS,
            self.__V_FILTER_BITRATE_LOWER, fallback=self.filter.bitrateLowerThan)
        self.filter.bitrateLowerThanValue = floor_ceil_int(cfg.getint(self.__S_FILTERS,
            self.__V_FILTER_BITRATE_LOWER_VALUE, fallback=self.filter.bitrateLowerThanValue),
            AudioStreamInfo.BITRATE_MIN, AudioStreamInfo.BITRATE_MAX)
        self.filter.bitrateGreaterThanValue = floor_ceil_int(cfg.getint(self.__S_FILTERS,
            self.__V_FILTER_BITRATE_GREATER_VALUE, fallback=self.filter.bitrateGreaterThanValue),
            AudioStreamInfo.BITRATE_MIN, AudioStreamInfo.BITRATE_MAX)

    def save(self):
        cfg = ConfigParser()
        cfg.add_section(self.__S_SETTINGS)
        cfg.add_section(self.__S_FILTERS)

        #
        cfg.set(self.__S_SETTINGS, self.__V_LASTDIR, self.lastDirectory)

        #
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BY_FILETYPES, str(self.filter.byFileTypes))
        cfg.set(self.__S_FILTERS, self.__V_FILTER_FILETYPES, self.filter.filetypes_to_str())

        #
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BY_LOSSLESS, str(self.filter.byLossless))
        cfg.set(self.__S_FILTERS, self.__V_FILTER_ONLY_LOSSLESS, str(self.filter.onlyLossless))

        #
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BY_RESOLUTION, str(self.filter.byResolution))
        cfg.set(self.__S_FILTERS, self.__V_FILTER_RESOLUTION, str(self.filter.resolution))

        #
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BY_BITRATE, str(self.filter.byBitrate))
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BITRATE_LOWER, str(self.filter.bitrateLowerThan))
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BITRATE_LOWER_VALUE, str(self.filter.bitrateLowerThanValue))
        cfg.set(self.__S_FILTERS, self.__V_FILTER_BITRATE_GREATER_VALUE, str(self.filter.bitrateGreaterThanValue))

        #
        with open(self.pathConfig, 'w+') as f:
            cfg.write(f)

    def __repr_fields__(self):
        return []


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    print(cfg)

    cfg.save()
