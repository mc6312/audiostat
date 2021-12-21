#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" AudioStat

    Copyright 2021 MC-6312

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>."""


import sys
from traceback import print_exception

try:
    from gtktools import *
    from gi.repository import Gtk#, Gdk, GObject, Pango, GLib
    #from gi.repository.GdkPixbuf import Pixbuf

    import mutagen
except ImportError as ex:
    print('** %s' % repr(ex))

    msg_dialog(None, 'Import error', repr(ex))
    sys.exit(255)

from warnings import warn

from collections import OrderedDict

from audiostat import *
from asconfig import *


class MainWnd():
    PAGE_START, PAGE_PROGRESS, PAGE_STATS = range(3)

    # столбцы TreeModel дерева статистики
    STC_NAME, STC_SAMPLERATE, STC_CHANNELS, STC_BITSPERSAMPLE,\
    STC_BITRATE, STC_LOSSY, STC_MISSINGTAGS, STC_LOWRES = range(8)

    def wnd_destroy(self, widget, data=None):
        #!!!
        self.stopScanning = True

        #!!!
        self.cfg.save()

        Gtk.main_quit()

    def __init__(self, _cfg):
        self.cfg = _cfg

        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'audiostat.ui')

        self.window = uibldr.get_object('wndMain')

        headerBar = uibldr.get_object('headerBar')

        headerBar.set_title(TITLE)
        headerBar.set_subtitle('v%s' % VERSION)

        isize = 128 #!!!
        self.window.set_icon(resldr.load_pixbuf('images/audiostat.svg',
            isize, isize))

        self.markIcon = load_system_icon('object-select-symbolic', Gtk.IconSize.MENU, False, symbolic=True)

        #
        self.pages, self.btnRun, self.boxFileCtls, self.btnCopyPath = get_ui_widgets(uibldr,
            'pages', 'btnRun', 'boxFileCtls', 'btnCopyPath')

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        # start page
        self.fcStartDir, self.entFileTypes = get_ui_widgets(uibldr,
            'fcStartDir', 'entFileTypes')

        # progress page
        self.labProgressPath, self.labProgressFiles,\
        self.labProgressAudioFiles, self.labProgressErrors,\
        self.progressBar = get_ui_widgets(uibldr,
            'labProgressPath', 'labProgressFiles', 'labProgressAudioFiles',
            'labProgressErrors', 'progressBar')

        # stats page
        swStats = uibldr.get_object('swStats')
        _ = WIDGET_BASE_HEIGHT * 32
        swStats.set_min_content_height(_)
        swStats.set_size_request(-1, _)

        self.tvStats = TreeViewShell.new_from_uibuilder(uibldr, 'tvStats')
        self.tvStats.view.set_size_request(WIDGET_BASE_WIDTH * 128, -1)

        self.tvSummary = TreeViewShell.new_from_uibuilder(uibldr, 'tvSummary')
        self.tvSampleRates = TreeViewShell.new_from_uibuilder(uibldr, 'tvSampleRates')
        self.tvBitsPerSample = TreeViewShell.new_from_uibuilder(uibldr, 'tvBitsPerSample')

        #
        self.entFileTypes.set_text(filetypes_to_str(self.cfg.fileTypes))

        #
        self.stopScanning = False

        self.window.show_all()
        self.__go_to_start_page()

        uibldr.connect_signals(self)

    def scan_statistics(self):
        self.stopScanning = False

        self.progressFiles = 0
        self.progressAudioFiles = 0
        self.progressErrors = 0

        # ключи - значения AudioStreamInfo.sampleRate, значения - кол-во файлов
        totalSampleRates = dict()

        # ключи - значения AudioStreamInfo.bitsPerSample, значения - кол-во файлов
        totalBitsPerSample = dict()

        # прочая статистика
        TS_LOSSY = 'Lossy'
        TS_LOWRES = 'Low res.'
        TS_MISTAGS = 'Missing tags'

        totalSummary = OrderedDict()
        totalSummary[TS_LOSSY] = 0
        totalSummary[TS_LOWRES] = 0
        totalSummary[TS_MISTAGS] = 0

        #
        self.cfg.fileTypes = str_to_filetypes(self.entFileTypes.get_text())

        def __scan_directory(destNode, fdir):
            """Обход подкаталога.

            Параметры:
                destNode    - Gtk.TreeIter,
                fdir        - строка, каталог.

            Возвращает экземпляр AudioDirectoryInfo."""

            dirinfo = AudioDirectoryInfo()

            self.labProgressPath.set_text(fdir)
            print('Scanning "%s"' % fdir, file=sys.stderr)

            def __next_error(msg):
                print(msg, file=sys.stderr)

                self.progressErrors += 1
                self.labProgressErrors.set_text(str(self.progressErrors))

            #TODO возможно, придётся как-то отслеживать выход за пределы fdir симлинками?
            for fname in os.listdir(fdir):
                if self.stopScanning:
                    return

                fpath = os.path.abspath(os.path.join(fdir, fname))

                if os.path.isdir(fpath):
                    # столбцы TreeStore:
                    # name, samplerate, channels, bitspersample, bitrate, lossy, missingtags
                    subNode = self.tvStats.store.append(destNode,
                        (fname, '', '', '', '', None, None, None))

                    subinfo = __scan_directory(subNode, fpath)

                    if not subinfo.nFiles:
                        # нафига нам пустые каталоги?
                        self.tvStats.store.remove(subNode)
                    else:
                        dirinfo.update_from_dir(subinfo)

                        # дополняем запись прожёванного каталога
                        self.tvStats.store.set(subNode,
                            (self.STC_SAMPLERATE, self.STC_CHANNELS,
                             self.STC_BITSPERSAMPLE, self.STC_BITRATE,
                             self.STC_LOSSY, self.STC_MISSINGTAGS,
                             self.STC_LOWRES),
                            (disp_int_range_k(subinfo.minInfo.sampleRate, subinfo.maxInfo.sampleRate),
                             disp_int_range(subinfo.minInfo.channels, subinfo.maxInfo.channels),
                             disp_int_range(subinfo.minInfo.bitsPerSample, subinfo.maxInfo.bitsPerSample),
                             disp_int_range_k(subinfo.minInfo.bitRate, subinfo.maxInfo.bitRate),
                             disp_bool(subinfo.minInfo.lossy, self.markIcon),
                             disp_bool(subinfo.minInfo.missingTags, self.markIcon),
                             disp_bool(subinfo.minInfo.lowRes, self.markIcon)))

                else:
                    self.progressFiles += 1
                    self.labProgressFiles.set_text(str(self.progressFiles))

                    r = get_audio_file_info(fpath, self.cfg.fileTypes)

                    if r.error:
                        'error reading file "%s" - %s' % (fname, r.error)
                    elif r.isAudio:
                        dirinfo.update_from_file(r)

                        # статистика по sampleRate
                        if r.sampleRate in totalSampleRates:
                            totalSampleRates[r.sampleRate] += 1
                        else:
                            totalSampleRates[r.sampleRate] = 1

                        # статистика по bitsPerSample
                        if r.bitsPerSample in totalBitsPerSample:
                            totalBitsPerSample[r.bitsPerSample] += 1
                        else:
                            totalBitsPerSample[r.bitsPerSample] = 1

                        # прочая статистика
                        if r.lossy:
                            totalSummary[TS_LOSSY] += 1

                        if r.lowRes:
                            totalSummary[TS_LOWRES] += 1

                        if r.missingTags:
                            totalSummary[TS_MISTAGS] += 1

                        #
                        self.progressAudioFiles += 1
                        self.labProgressAudioFiles.set_text(str(self.progressAudioFiles))

                        # захерачим файл в статистику
                        # столбцы TreeStore:
                        # name, samplerate, channels, bitspersample, bitrate, lossy, missingtags, lowres
                        self.tvStats.store.append(destNode,
                            (fname,
                             disp_int_val_k(r.sampleRate),
                             disp_int_val(r.channels),
                             disp_int_val(r.bitsPerSample),
                             disp_int_val_k(r.bitRate),
                             disp_bool(r.lossy, self.markIcon),
                             disp_bool(r.missingTags, self.markIcon),
                             disp_bool(r.lowRes, self.markIcon)))

                    #error, lossy, mime, sampleRate, channels, bitsPerSample, missingTags

                    #
                    self.progressBar.pulse()
                    flush_gtk_events()

            return dirinfo

        #
        # собираем статистику
        #
        self.tvStats.refresh_begin()

        print('*** Starting collecting statistics ***', file=sys.stderr)
        self.cfg.lastDirectory = self.fcStartDir.get_current_folder()
        print('Searching audio files in %s' % self.cfg.lastDirectory, file=sys.stderr)

        dirinfo = __scan_directory(None, self.cfg.lastDirectory)

        self.tvStats.sortColumn = self.STC_NAME
        self.tvStats.refresh_end()

        if self.stopScanning:
            self.__go_to_start_page()
            return

        #
        # вроде как всё нормально - показываем статистику
        #

        def fill_summary_table(srcd, tv, tostr):
            __pcts = lambda n: int(float(n) / self.progressAudioFiles * 100.0)
            __s_pcts = lambda n, p: '%d (%d%%)' % (n, p)

            tv.refresh_begin()

            for param, nfiles in sorted(srcd.items()):
                if param != 0:
                    pcts = __pcts(nfiles)
                    tv.store.append((tostr(param),
                        __s_pcts(nfiles, pcts),
                        pcts))

            # сюда попадают файлы, где нет соотв. параметра в метаданных
            if 0 in srcd:
                pcts = __pcts(nfiles)
                tv.store.append(('other',
                    __s_pcts(nfiles, pcts),
                    __pcts(nfiles)))

            tv.refresh_end()

        # заполняем таблицу sampleRates
        fill_summary_table(totalSampleRates, self.tvSampleRates, disp_int_val_k)

        # заполняем таблицу bitsPerSample
        fill_summary_table(totalBitsPerSample, self.tvBitsPerSample, disp_int_val)

        # заполняем прочую статистику
        fill_summary_table(totalSummary, self.tvSummary, str)

        #
        self.btnRun.set_label('Scan other directory')
        self.pages.set_current_page(self.PAGE_STATS)
        self.boxFileCtls.set_sensitive(True)
        self.boxFileCtls.set_visible(True)

    def selStats_changed(self, _):
        self.btnCopyPath.set_sensitive(self.tvStats.get_selected_iter() is not None)

    def copy_selected_path(self):
        """Копирование полного пути выбранного файла или каталога
        в буфер обмена."""

        itr = self.tvStats.get_selected_iter()
        if not itr:
            return

        path = []

        while itr is not None:
            path.insert(0, self.tvStats.store.get_value(itr, self.STC_NAME))

            itr = self.tvStats.store.iter_parent(itr)

        self.clipboard.set_text(os.path.join(self.cfg.lastDirectory, *path), -1)

    def tvStats_row_activated(self, tv, path, col):
        self.copy_selected_path()

    def btnCopyPath_clicked(self, btn):
        self.copy_selected_path()

    def __go_to_start_page(self):
        self.fcStartDir.set_current_folder(self.cfg.lastDirectory)
        self.pages.set_current_page(self.PAGE_START)
        self.btnRun.set_label('Start')

        self.boxFileCtls.set_visible(False)
        self.boxFileCtls.set_sensitive(False)

    def btnRun_clicked(self, btn):
        p = self.pages.get_current_page()

        if p == self.PAGE_START:
            self.btnRun.set_label('Stop')
            self.pages.set_current_page(self.PAGE_PROGRESS)
            self.scan_statistics()
        else:
            # p == self.PAGE_STATS
            if p == self.PAGE_PROGRESS:
                self.stopScanning = True

            self.__go_to_start_page()

    def handle_unhandled(self, exc_type, exc_value, exc_traceback):
        # дабы не зациклиться, если че рухнет в этом обработчике
        sys.excepthook = sys.__excepthook__

        msg = 'Unhandled exception - %s' % exc_type.__name__

        print('** %s' % msg, file=sys.stderr)
        print_exception(exc_type, exc_value, exc_traceback)

        msg_dialog(self.window, 'Error', msg)

        sys.exit(255)

    def main(self):
        sys.excepthook = self.handle_unhandled
        Gtk.main()


def main():
    cfg = Config()
    MainWnd(cfg).main()

    return 0


if __name__ == '__main__':
    main()
