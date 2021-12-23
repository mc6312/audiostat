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

from gtktools import *
from gi.repository import Gtk#, Gdk, GObject, Pango, GLib
#from gi.repository.GdkPixbuf import Pixbuf


import mutagen

from warnings import warn

from collections import OrderedDict

from ascommon import *
from audiostat import *
from asconfig import *


class MainWnd():
    PAGE_START, PAGE_PROGRESS, PAGE_STATS = range(3)

    # столбцы TreeModel дерева статистики
    STC_NAME, STC_SAMPLERATE, STC_CHANNELS, STC_BITSPERSAMPLE,\
    STC_BITRATE, STC_LOSSY, STC_MISSINGTAGS, STC_LOWRES = range(8)

    # столбцы TreeModel списка типов файлов
    FTC_CHECKED, FTC_NAME = range(2)

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

        # индекс в кортеже - AudioStreamInfo.RESOLUTION_*
        self.resolutionIcons = tuple(map(lambda s: load_system_icon(s, Gtk.IconSize.MENU, symbolic=True),
            ('non-starred', 'semi-starred', 'starred')))

        #
        self.pages, self.btnRun, self.boxFileCtls, self.btnCopyPath = get_ui_widgets(uibldr,
            'pages', 'btnRun', 'boxFileCtls', 'btnCopyPath')

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        #
        # start page
        #
        self.fcStartDir = uibldr.get_object('fcStartDir')
        # потому как текущая версия Glade (3.38.x) - косяк на косяке
        self.fcStartDir.set_action(Gtk.FileChooserAction.SELECT_FOLDER)

        #
        # фильтрация по типам файлов
        self.chkFilterFileTypes, self.swFilterFileTypes = get_ui_widgets(uibldr,
            'chkFilterFileTypes', 'swFilterFileTypes')
        self.tvFilterFileTypes = TreeViewShell.new_from_uibuilder(uibldr, 'tvFilterFileTypes')

        self.chkFilterFileTypes.set_active(self.cfg.filter.byFileTypes)

        self.swFilterFileTypes.set_min_content_height(WIDGET_BASE_HEIGHT * 10)
        self.swFilterFileTypes.set_sensitive(self.cfg.filter.byFileTypes)

        for ftname, ftexts in AUDIO_FILE_TYPES:
            self.tvFilterFileTypes.store.append((ftexts & self.cfg.filter.fileTypes,
                ftname))

        #
        # фильтрация по формату - без потерь/с потерями
        self.boxFilterByFormat,\
        self.chkFilterByLossless, self.rbtnFilterFmtLossless = get_ui_widgets(uibldr,
            'boxFilterByFormat', 'chkFilterByLossless', 'rbtnFilterFmtLossless')

        # здесь и далее - названия виджетов соответствуют полям AudioFileFilter,
        # и их состояние прямо здесь устанавливается из содержимого конфига
        self.chkFilterByLossless.set_active(self.cfg.filter.byLossless)
        self.boxFilterByFormat.set_sensitive(self.cfg.filter.byLossless)

        self.rbtnFilterFmtLossless.set_active(self.cfg.filter.onlyLossless)

        #
        # фильтрация по разрешению
        self.boxFilterByResolution, self.chkFilterByResolution,\
        self.rbtnFilterByResolutionLow, self.rbtnFilterByResolutionStd,\
        self.rbtnFilterByResolutionHigh = get_ui_widgets(uibldr,
            'boxFilterByResolution', 'chkFilterByResolution',
            'rbtnFilterByResolutionLow', 'rbtnFilterByResolutionStd', 'rbtnFilterByResolutionHigh')

        self.chkFilterByResolution.set_active(self.cfg.filter.byResolution)
        self.boxFilterByResolution.set_sensitive(self.cfg.filter.byResolution)

        if self.cfg.filter.resolution == AudioStreamInfo.RESOLUTION_LOW:
            rb = self.rbtnFilterByResolutionLow
        elif self.cfg.filter.resolution == AudioStreamInfo.RESOLUTION_STANDARD:
            rb = self.rbtnFilterByResolutionStd
        else:
            rb = self.rbtnFilterByResolutionHigh

        rb.set_active(True)

        #
        # фильтрация по битрейту
        self.chkFilterByBitrate, self.gridFilterByBitrate,\
        self.rbtnFilterBRLowerThan, self.rbtnFilterBRGreaterThan,\
        self.entFilterBitrateMax, self.entFilterBitrateMin,\
        adjEntFilterBitrateGreater, adjEntFilterBitrateLower = get_ui_widgets(uibldr,
            'chkFilterByBitrate', 'gridFilterByBitrate',
            'rbtnFilterBRLowerThan', 'rbtnFilterBRGreaterThan',
            'entFilterBitrateMax', 'entFilterBitrateMin',
            'adjEntFilterBitrateGreater', 'adjEntFilterBitrateLower')

        for adj in (adjEntFilterBitrateGreater, adjEntFilterBitrateLower):
            adj.set_upper(AudioStreamInfo.BITRATE_MAX)
            adj.set_lower(AudioStreamInfo.BITRATE_MIN)

        self.chkFilterByBitrate.set_active(self.cfg.filter.byBitrate)
        self.gridFilterByBitrate.set_sensitive(self.cfg.filter.byBitrate)

        if self.cfg.filter.bitrateLowerThan:
            rb = self.rbtnFilterBRLowerThan
        else:
            rb = self.rbtnFilterBRGreaterThan

        self.entFilterBitrateMax.set_value(self.cfg.filter.bitrateLowerThanValue)
        self.entFilterBitrateMin.set_value(self.cfg.filter.bitrateGreaterThanValue)

        rb.set_active(True)

        #
        # progress page
        #
        self.labProgressPath, self.labProgressFiles,\
        self.labProgressAudioFiles, self.labProgressErrors,\
        self.progressBar = get_ui_widgets(uibldr,
            'labProgressPath', 'labProgressFiles', 'labProgressAudioFiles',
            'labProgressErrors', 'progressBar')

        #
        # stats page
        #
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
        #self.entFileTypes.set_text(filetypes_to_str(self.cfg.fileTypes))

        #
        self.stopScanning = False

        self.window.show_all()
        self.__go_to_start_page()

        uibldr.connect_signals(self)

    def chkFilterFileTypes_toggled(self, cb):
        self.cfg.filter.byFileTypes = cb.get_active()
        self.swFilterFileTypes.set_sensitive(self.cfg.filter.byFileTypes)

    def chkFilterByLossless_toggled(self, cb):
        self.cfg.filter.byLossless = cb.get_active()
        self.boxFilterByFormat.set_sensitive(self.cfg.filter.byLossless)

    def rbtnFilterFmtLossless_toggled(self, rb):
        self.cfg.filter.onlyLossless = rb.get_active()

    def rbtnFilterFmtLossy_toggled(self, rb):
        self.cfg.filter.onlyLossless = not rb.get_active()

    def chkFilterByResolution_toggled(self, cb):
        self.cfg.filter.byResolution = cb.get_active()
        self.boxFilterByResolution.set_sensitive(self.cfg.filter.byResolution)

    def rbtnFilterByResolutionLow_toggled(self, rb):
        if rb.get_active():
            self.cfg.filter.resolution = AudioStreamInfo.RESOLUTION_LOW

    def rbtnFilterByResolutionStd_toggled(self, rb):
        if rb.get_active():
            self.cfg.filter.resolution = AudioStreamInfo.RESOLUTION_STANDARD

    def rbtnFilterByResolutionHigh_toggled(self, rb):
        if rb.get_active():
            self.cfg.filter.resolution = AudioStreamInfo.RESOLUTION_HIGH

    def chkFilterByBitrate_toggled(self, cb):
        self.cfg.filter.byBitrate = cb.get_active()
        self.gridFilterByBitrate.set_sensitive(self.cfg.filter.byBitrate)

    def rbtnFilterBRLowerThan_toggled(self, rb):
        self.cfg.filter.bitrateLowerThan = rb.get_active()

    def rbtnFilterBRGreaterThan_toggled(self, rb):
        self.cfg.filter.bitrateLowerThan = not rb.get_active()

    def entFilterBitrateMax_value_changed(self, sb):
        self.cfg.filter.bitrateLowerThanValue = sb.get_value_as_int()

    def entFilterBitrateMin_value_changed(self, sb):
        self.cfg.filter.bitrateGreaterThanValue = sb.get_value_as_int()

    def __toggle_filetype(self, path):
        itr = self.tvFilterFileTypes.store.get_iter(path)
        ix = path.get_indices()[0]

        v = not self.tvFilterFileTypes.store.get_value(itr, self.FTC_CHECKED)
        self.tvFilterFileTypes.store.set_value(itr, self.FTC_CHECKED, v)

        if v:
            self.cfg.filter.fileTypes |= AUDIO_FILE_TYPES[ix].exts
        else:
            self.cfg.filter.fileTypes -= AUDIO_FILE_TYPES[ix].exts

    def crFFTcheck_toggled(self, crt, path):
        """Переключение чекбокса в списке типов файлов"""

        # path приезжает как строка!
        self.__toggle_filetype(Gtk.TreePath.new_from_string(path))

    def tvFilterFileTypes_row_activated(self, tv, path, col):
        """Двойной клик по строке в списке типов файлов"""

        # path приезжает как Gtk.TreePath
        # (см. метод выше - ай спасибо гномеры за "единообразие!")
        self.__toggle_filetype(path)

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

        TS_BY_RES = ('Low res.',    # AudioStreamInfo.RESOLUTION_LOW
                     'Std. res.',   # AudioStreamInfo.RESOLUTION_STANDARD
                     'High res.',   # AudioStreamInfo.RESOLUTION_HIGH
                     )

        TS_MISTAGS = 'Missing tags'

        totalSummary = OrderedDict()

        for nres in TS_BY_RES:
            totalSummary[nres] = 0

        totalSummary[TS_LOSSY] = 0
        totalSummary[TS_MISTAGS] = 0

        #
        self.cfg.fileTypes = DEFAULT_AUDIO_FILE_EXTS
        #TODO допилить выбор типов файлов
        warn('file type selection must be implemented!')
        #str_to_filetypes(self.entFileTypes.get_text())

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
                             self.resolutionIcons[subinfo.minInfo.resolution],
                             ))

                else:
                    self.progressFiles += 1
                    self.labProgressFiles.set_text(str(self.progressFiles))

                    nfo = self.cfg.filter.get_audio_file_info(fpath)

                    if nfo:
                        if nfo.error:
                            __next_error('error reading file "%s" - %s' % (fname, nfo.error))
                        else:
                            dirinfo.update_from_file(nfo)

                            # статистика по sampleRate
                            if nfo.sampleRate in totalSampleRates:
                                totalSampleRates[nfo.sampleRate] += 1
                            else:
                                totalSampleRates[nfo.sampleRate] = 1

                            # статистика по bitsPerSample
                            if nfo.bitsPerSample in totalBitsPerSample:
                                totalBitsPerSample[nfo.bitsPerSample] += 1
                            else:
                                totalBitsPerSample[nfo.bitsPerSample] = 1

                            # прочая статистика
                            if nfo.lossy:
                                totalSummary[TS_LOSSY] += 1

                            for ixres, nres in enumerate(TS_BY_RES):
                                if nfo.resolution == ixres:
                                    totalSummary[nres] += 1

                            if nfo.missingTags:
                                totalSummary[TS_MISTAGS] += 1

                            #
                            self.progressAudioFiles += 1
                            self.labProgressAudioFiles.set_text(str(self.progressAudioFiles))

                            # захерачим файл в статистику
                            # столбцы TreeStore:
                            # name, samplerate, channels, bitspersample, bitrate, lossy, missingtags, lowres
                            self.tvStats.store.append(destNode,
                                (fname,
                                 disp_int_val_k(nfo.sampleRate),
                                 disp_int_val(nfo.channels),
                                 disp_int_val(nfo.bitsPerSample),
                                 disp_int_val_k(nfo.bitRate),
                                 disp_bool(nfo.lossy, self.markIcon),
                                 disp_bool(nfo.missingTags, self.markIcon),
                                 self.resolutionIcons[nfo.resolution],
                                 ))

                        #error, lossy, mime, sampleRate, channels, bitsPerSample, missingTags

                    #
                    self.progressBar.pulse()
                    flush_gtk_events()

            return dirinfo

        #
        # собираем статистику
        #
        self.tvStats.refresh_begin()

        print('*** Starting collecting statistics in %s' % self.cfg.lastDirectory, file=sys.stderr)

        dirinfo = __scan_directory(None, self.cfg.lastDirectory)

        self.tvStats.sortColumn = self.STC_NAME
        self.tvStats.refresh_end()

        if self.stopScanning:
            self.__go_to_start_page()
            return

        #
        # вроде как всё нормально - показываем статистику
        #

        def fill_summary_table(srcd, tv, tostr, _sort):
            __pcts = lambda n: int(float(n) / self.progressAudioFiles * 100.0)
            __s_pcts = lambda n, p: '%d (%d%%)' % (n, p)

            tv.refresh_begin()

            dlst = srcd.items()
            if _sort:
                dlst = sorted(dlst)

            for param, nfiles in dlst:
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
        fill_summary_table(totalSampleRates, self.tvSampleRates, disp_int_val_k, True)

        # заполняем таблицу bitsPerSample
        fill_summary_table(totalBitsPerSample, self.tvBitsPerSample, disp_int_val, True)

        # заполняем прочую статистику
        fill_summary_table(totalSummary, self.tvSummary, str, False)

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

    def fcStartDir_current_folder_changed(self, fc):
        self.cfg.lastDirectory = self.fcStartDir.get_current_folder()
        print('Search directory changed to "%s"' % self.cfg.lastDirectory)

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
