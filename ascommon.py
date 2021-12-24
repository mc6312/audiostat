#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" ascommon.py

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
VERSION = '1.2'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)
COPYLEFT = '🄯 2021 MC-6312'
URL = 'https://github.com/mc6312/audiostat'


def disp_int_val_k(i):
    return '?' if not i else i if isinstance(i, str) else '%.1f' % (i / 1000.0)


def disp_int_val(i):
    return '?' if not i else str(i)


def disp_int_range(a, b):
    if a == b:
        return disp_int_val(a)
    else:
        return '%s - %s' % (disp_int_val(a), disp_int_val(b))


def disp_int_range_k(a, b):
    if a == b:
        return disp_int_val_k(a)
    else:
        return '%s - %s' % (disp_int_val_k(a), disp_int_val_k(b))


def disp_bool(b, vtrue):
    return None if not b else vtrue


def floor_ceil_int(v, vmin, vmax):
    if v < vmin:
        return vmin
    elif v > vmax:
        return vmax
    else:
        return v


class Representable():
    """Класс-костыль для упрощения написания метода __repr__()
    в классах с наследованием, для облегчения отладки классов.
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
        """Метод, вызываемый стандартной функцией repr().
        Вызывает метод __repr_fields__(), форматирует
        полученный от него список полей.
        Если список был пуст, пытается обработать self.__dict__
        и self.__slots__, если они есть.
        Возвращает отформатированную строку с именем класса и перечислением
        полей с их значениями."""

        def __rfld(name, value):
            if isinstance(value, str):
                s = '"%s"' % value
            elif isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
                s = str(value)
            else:
                s = repr(value)

            return '%s=%s' % (name, s)

        flds = self.__repr_fields__()

        if not flds:
            if hasattr(self, '__dict__'):
                flds = self.__dict__.items()
            elif hasattr(self, '__slots__'):
                flds = self.__slots__.items()

        return '%s(%s)' % (self.__class__.__name__,
            ', '.join(map(lambda f: __rfld(*f), flds)))


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    class Dummy(Representable):
        pass

    class DummyWithFields(Representable):
        def __init__(self):
            self.fieldName = 1

    class DummyBroken(Representable):
        def __repr_fields__(self):
            return []

        def __init__(self):
            self.fieldName = 1

    print(repr(Dummy()))
    print(repr(DummyWithFields()))
    print(repr(DummyBroken()))
