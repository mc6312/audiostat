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
    __V_LASTDIR = 'lastDirectory'

    __S_FILTERS = 'filters'

    def __init__(self):
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

    def load(self):
        if not os.path.exists(self.pathConfig):
            return

        # пытаемся загрузить конфиг
        cfg = ConfigParser()
        cfg.read(self.pathConfig)

        #
        # тащим значения из конфига в поля сего объекта
        #

        # основные
        self.lastDirectory = os.path.expanduser(cfg.get(self.__S_SETTINGS,
            self.__V_LASTDIR, fallback=self.lastDirectory))

        # фильтрация
        for pname in AudioFileFilter.PARAMETERS:
            s = cfg.get(self.__S_FILTERS, pname, fallback=None)

            if s is not None:
                try:
                    self.filter.set_parameter_str(pname, s)
                except Exception as ex:
                    raise ValueError('Invalid parameter "%s" in section "%s" of file "%s" -  %s' % (
                                     pname, self.__S_FILTERS, self.pathConfig, str(ex)))

    def save(self):
        cfg = ConfigParser()
        cfg.add_section(self.__S_SETTINGS)
        cfg.add_section(self.__S_FILTERS)

        # основные
        cfg.set(self.__S_SETTINGS, self.__V_LASTDIR, self.lastDirectory)

        # фильтрация
        for pname in AudioFileFilter.PARAMETERS:
            cfg.set(self.__S_FILTERS, pname, self.filter.get_parameter_str(pname))
        #
        with open(self.pathConfig, 'w+') as f:
            cfg.write(f)

    def __repr_fields__(self):
        return []


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    print('\033[1mdefaults:\033[0m\n', cfg)

    cfg.load()
    print('\033[1mloaded:\033[0m\n', cfg)

    cfg.save()
