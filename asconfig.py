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

from audiostat import AUDIO_FILE_TYPES


def str_to_filetypes(fts):
    return set(map(lambda s: s.lower(), fts.split(None)))


def filetypes_to_str(fts):
    return ' '.join(sorted(fts))


class Config():
    __S_SETTINGS = 'settings'
    __V_LASTDIR = 'last-directory'
    __V_FILETYPES = 'file-types'

    def __init__(self):
        self.lastDirectory = os.path.expanduser('~')
        self.fileTypes = AUDIO_FILE_TYPES

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
        self.lastDirectory = os.path.expanduser(cfg.get(self.__S_SETTINGS,
            self.__V_LASTDIR, fallback=self.lastDirectory))

        self.fileTypes = str_to_filetypes(cfg.get(self.__S_SETTINGS,
            self.__V_FILETYPES, fallback=filetypes_to_str(self.fileTypes)))

    def save(self):
        cfg = ConfigParser()
        cfg.add_section(self.__S_SETTINGS)

        cfg.set(self.__S_SETTINGS, self.__V_LASTDIR, self.lastDirectory)
        cfg.set(self.__S_SETTINGS, self.__V_FILETYPES, filetypes_to_str(self.fileTypes))

        with open(self.pathConfig, 'w+') as f:
            cfg.write(f)

    def __repr__(self):
        return '%s(pathConfig="%s", lastDirectory="%s", fileTypes=%s)' % (self.__class__.__name__,
            self.pathConfig, self.lastDirectory, self.fileTypes)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    print(cfg)

    cfg.save()
