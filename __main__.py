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
from gi.repository import Gtk
from gi.repository.GLib import markup_escape_text


import mutagen

from warnings import warn

from collections import OrderedDict

from ascommon import *
from audiostat import *
from asconfig import *


class MainWnd():
    PAGE_START, PAGE_RESULT = range(2)
    PHASE_START_PAGE, PHASE_SCANNING, PHASE_RESULT = range(3)

    # столбцы TreeModel дерева статистики
    STC_NAME, STC_SAMPLERATE, STC_CHANNELS, STC_BITSPERSAMPLE,\
    STC_BITRATE, STC_LOSSY, STC_MISSINGTAGS, STC_LOWRES,\
    STC_ERRORS, STC_HINT = range(10)

    # столбцы TreeModel списка типов файлов
    FTC_CHECKED, FTC_NAME = range(2)

    def wnd_destroy(self, widget, data=None):
        #!!!
        self.stopScanning = True

        #!!!
        self.cfg.save()

        Gtk.main_quit()

    def __init__(self):
        self.cfg = Config()
        self.cfg.load()

        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'audiostat.ui')

        self.window = uibldr.get_object('wndMain')

        headerBar = uibldr.get_object('headerBar')

        headerBar.set_title(TITLE)
        headerBar.set_subtitle('v%s' % VERSION)

        isize = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 4 #!!!
        logo = resldr.load_pixbuf('images/audiostat.svg', isize, isize)
        self.window.set_icon(logo)

        self.iconLossyAudio = load_system_icon('network-cellular-signal-weak-symbolic', Gtk.IconSize.MENU, False, symbolic=True)
        self.iconMissingTags = load_system_icon('dialog-warning', Gtk.IconSize.MENU, False, symbolic=True)
        self.iconErrors = load_system_icon('dialog-error', Gtk.IconSize.MENU, False, symbolic=True)

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

        self.boxStartSettings, self.fcStartDir = get_ui_widgets(uibldr,
            'boxStartSettings', 'fcStartDir')

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
        self.chkFilterByLossless, self.cboxFilterLossless = get_ui_widgets(uibldr,
            'chkFilterByLossless', 'cboxFilterLossless')

        # здесь и далее - названия виджетов примерно соответствуют полям AudioFileFilter,
        # и их состояние прямо здесь устанавливается из содержимого конфига
        self.chkFilterByLossless.set_active(self.cfg.filter.byLossless)
        self.cboxFilterLossless.set_sensitive(self.cfg.filter.byLossless)

        self.cboxFilterLossless.set_active(int(self.cfg.filter.onlyLossless))

        #
        # фильтрация по разрешению
        self.chkFilterByResolution, self.cboxFilterResolution = get_ui_widgets(uibldr,
            'chkFilterByResolution', 'cboxFilterResolution')

        self.chkFilterByResolution.set_active(self.cfg.filter.byResolution)
        self.cboxFilterResolution.set_sensitive(self.cfg.filter.byResolution)

        self.cboxFilterResolution.set_active(self.cfg.filter.resolution)

        #
        # фильтрация по битрейту
        self.chkFilterByBitrate, self.gridFilterByBitrate,\
        self.rbtnFilterBRLowerThan, self.rbtnFilterBRGreaterThan,\
        self.spinFilterBitrateMax, self.spinFilterBitrateMin,\
        adjEntFilterBitrateGreater, adjEntFilterBitrateLower = get_ui_widgets(uibldr,
            'chkFilterByBitrate', 'gridFilterByBitrate',
            'rbtnFilterBRLowerThan', 'rbtnFilterBRGreaterThan',
            'spinFilterBitrateMax', 'spinFilterBitrateMin',
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

        self.spinFilterBitrateMax.set_value(self.cfg.filter.bitrateLowerThanValue)
        self.spinFilterBitrateMin.set_value(self.cfg.filter.bitrateGreaterThanValue)

        rb.set_active(True)

        #
        # фильтрация по наличию параметров аудиопотока
        self.chkFilterByContainsStreamParams, self.cboxFilterContainsStreamParams = get_ui_widgets(uibldr,
            'chkFilterByContainsStreamParams', 'cboxFilterContainsStreamParams')

        self.chkFilterByContainsStreamParams.set_active(self.cfg.filter.byContainsStreamParameters)
        self.cboxFilterContainsStreamParams.set_sensitive(self.cfg.filter.byContainsStreamParameters)

        self.cboxFilterContainsStreamParams.set_active(int(self.cfg.filter.onlyContainsStreamParameters))

        #
        # фильтрация по наличию ошибок в метаданных
        self.chkFilterByErrors, self.cboxFilterErrors = get_ui_widgets(uibldr,
            'chkFilterByErrors', 'cboxFilterErrors')

        self.chkFilterByErrors.set_active(self.cfg.filter.byErrors)
        self.cboxFilterErrors.set_sensitive(self.cfg.filter.byErrors)

        self.cboxFilterErrors.set_active(self.cfg.filter.onlyWithErrors)

        #
        # фильтрация по наличию важных тэгов
        self.chkFilterByTags, self.cboxFilterTags = get_ui_widgets(uibldr,
            'chkFilterByTags', 'cboxFilterTags')

        self.chkFilterByTags.set_active(self.cfg.filter.byMissingTags)
        self.cboxFilterTags.set_sensitive(self.cfg.filter.byMissingTags)

        self.cboxFilterTags.set_active(int(self.cfg.filter.onlyMissingTags))

        #
        # progress
        #
        self.boxProgress, self.labProgressPath,\
        self.labProgressFiles, self.labProgressFileCount,\
        self.progressBar = get_ui_widgets(uibldr,
            'boxProgress', 'labProgressPath',
            'labProgressFiles', 'labProgressFileCount',
            'progressBar')

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
        #
        self.dlgAbout = uibldr.get_object('dlgAbout')
        self.dlgAbout.set_logo(logo)
        self.dlgAbout.set_program_name(TITLE)
        #self.dlgAbout.set_comments(SUB_TITLE)
        self.dlgAbout.set_version('v%s' % VERSION)
        self.dlgAbout.set_copyright(COPYLEFT)
        self.dlgAbout.set_website(URL)
        self.dlgAbout.set_website_label(URL)

        #
        self.stopScanning = False
        self.phase = self.PHASE_START_PAGE

        self.window.show_all()

        self.phase_start_page()

        uibldr.connect_signals(self)

    def mnuMainAbout_activate(self, wgt):
        self.dlgAbout.show_all()
        self.dlgAbout.run()
        self.dlgAbout.hide()

    # фильтрация по типам файлов
    def chkFilterFileTypes_toggled(self, cb):
        self.cfg.filter.byFileTypes = cb.get_active()
        self.swFilterFileTypes.set_sensitive(self.cfg.filter.byFileTypes)

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

    # фильтрация по формату (с потерями/без потерь)
    def chkFilterByLossless_toggled(self, cb):
        self.cfg.filter.byLossless = cb.get_active()
        self.cboxFilterLossless.set_sensitive(self.cfg.filter.byLossless)

    def cboxFilterLossless_changed(self, cbox):
        self.cfg.filter.onlyLossless = cbox.get_active() > 0

    # фильтрация по наличию ошибок
    def chkFilterByErrors_toggled(self, cb):
        self.cfg.filter.byErrors = cb.get_active()
        self.cboxFilterErrors.set_sensitive(self.cfg.filter.byErrors)

    def cboxFilterErrors_changed(self, cbox):
        self.cfg.filter.onlyWithErrors = cbox.get_active() > 0

    # фильтрация по разрешению аудио
    def chkFilterByResolution_toggled(self, cb):
        self.cfg.filter.byResolution = cb.get_active()
        self.cboxFilterResolution.set_sensitive(self.cfg.filter.byResolution)

    def cboxFilterResolution_changed(self, cbox):
        self.cfg.filter.resolution = cbox.get_active()

    # фильтрация по битрейту
    def chkFilterByBitrate_toggled(self, cb):
        self.cfg.filter.byBitrate = cb.get_active()
        self.gridFilterByBitrate.set_sensitive(self.cfg.filter.byBitrate)

    def rbtnFilterBRLowerThan_toggled(self, rb):
        self.cfg.filter.bitrateLowerThan = rb.get_active()

    def rbtnFilterBRGreaterThan_toggled(self, rb):
        self.cfg.filter.bitrateLowerThan = not rb.get_active()

    def spinFilterBitrateMax_value_changed(self, sb):
        self.cfg.filter.bitrateLowerThanValue = sb.get_value_as_int()

    def spinFilterBitrateMin_value_changed(self, sb):
        self.cfg.filter.bitrateGreaterThanValue = sb.get_value_as_int()

    # фильтрация по наличию параметров аудиопотока
    def chkFilterByContainsStreamParams_toggled(self, cb):
        self.cfg.filter.byContainsStreamParameters = cb.get_active()
        self.cboxFilterContainsStreamParams.set_sensitive(self.cfg.filter.byContainsStreamParameters)

    def cboxFilterContainsStreamParams_changed(self, cbox):
        self.cfg.filter.onlyContainsStreamParameters = cbox.get_active() > 0

    # фильтрация по наличию важных тэгов
    def chkFilterByTags_toggled(self, cb):
        self.cfg.filter.byMissingTags = cb.get_active()
        self.cboxFilterTags.set_sensitive(self.cfg.filter.byMissingTags)

    def cboxFilterTags_changed(self, cbox):
        self.cfg.filter.onlyMissingTags = cbox.get_active() > 0

    def scan_statistics(self):
        """Сбор статистики"""

        self.stopScanning = False

        self.progressAudioFiles = 0

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
        TS_WITH_ERRORS = 'With errors'

        totalSummary = OrderedDict()

        #TODO когда-нибудь всё это отрефакторить
        class SummaryTableItem():
            __slots__ = 'value', 'icon'

            def __init__(self, v, i):
                self.value = v
                self.icon = i

        for ix,nres in enumerate(TS_BY_RES):
            totalSummary[nres] = SummaryTableItem(0, self.resolutionIcons[ix])

        totalSummary[TS_LOSSY] = SummaryTableItem(0, self.iconLossyAudio)
        totalSummary[TS_MISTAGS] = SummaryTableItem(0, self.iconMissingTags)
        totalSummary[TS_WITH_ERRORS] = SummaryTableItem(0, self.iconErrors)

        #
        # проход 1: сбор списка файлов на обработку
        #
        self.labProgressFiles.set_text('Files found:')

        def __scan_progress(fpath, nFiles):
            self.labProgressPath.set_text(fpath)
            self.labProgressFileCount.set_text(str(nFiles))
            self.progressBar.pulse()
            flush_gtk_events()
            return True

        ftree = AudioFileList(self.cfg.lastDirectory, self.cfg.filter, __scan_progress)

        self.labProgressFiles.set_text('Files processed:')

        #
        # проход 2: обработка найденных файлов
        #
        self.currentFileNumber = 0

        def __process_diritem(node, diritem, parent):
            fpath = os.path.join(parent, diritem.name)

            if diritem.isdir:
                # подкаталог
                self.labProgressPath.set_text(fpath)
                print('Scanning "%s"' % fpath, file=sys.stderr)

                raise NotImplementedError('всю эту хуйню надо переписать!')

                if not fprocess(fpath, **kwdata):
                    return False

                self.currentFileNumber += 1
            else:
                if not fprogress(fpath, self.currentFileNumber, self.totalFiles):
                    return False

                for i in diritem.children:
                    if not __process_diritem(i, fpath):
                        return False

            return True

        self.currentFileNumber = 0
        __process_diritem(self.files, '')

        return

        def __process_directory(destNode, fdir):
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

            __disp_resolution = lambda _nfo: None if _nfo.resolution is None else self.resolutionIcons[_nfo.resolution]

            #TODO возможно, придётся как-то отслеживать выход за пределы fdir симлинками?
            for fname in os.listdir(fdir):
                if self.stopScanning:
                    return

                fpath = os.path.abspath(os.path.join(fdir, fname))

                if os.path.isdir(fpath):
                    subNode = self.tvStats.store.append(destNode,
                        (fname, '', '', '', '', None, None, None, None, None))

                    subinfo = __scan_directory(subNode, fpath)

                    if not subinfo or not subinfo.nFiles:
                        # нафига нам пустые каталоги?
                        self.tvStats.store.remove(subNode)
                    else:
                        dirinfo.update_from_dir(subinfo)

                        # дополняем запись прожёванного каталога
                        self.tvStats.store.set(subNode,
                            (self.STC_SAMPLERATE, self.STC_CHANNELS,
                             self.STC_BITSPERSAMPLE, self.STC_BITRATE,
                             self.STC_LOSSY, self.STC_MISSINGTAGS,
                             self.STC_LOWRES, self.STC_ERRORS, self.STC_HINT),
                            (disp_int_range_k(subinfo.minInfo.sampleRate, subinfo.maxInfo.sampleRate),
                             disp_int_range(subinfo.minInfo.channels, subinfo.maxInfo.channels),
                             disp_int_range(subinfo.minInfo.bitsPerSample, subinfo.maxInfo.bitsPerSample),
                             disp_int_range(subinfo.minInfo.bitRate, subinfo.maxInfo.bitRate),
                             disp_bool(subinfo.minInfo.lossy, self.iconLossyAudio),
                             disp_bool(subinfo.minInfo.missingTags, self.iconMissingTags),
                             __disp_resolution(subinfo.minInfo),
                             disp_bool(subinfo.nErrors > 0, self.iconErrors),
                             markup_escape_text(subinfo.get_hint_str()),
                             ))

                else:
                    if self.cfg.filter.file_match_types(fname):
                        nfo = self.cfg.filter.get_audio_file_info(fpath)

                        if nfo:
                            if nfo.error:
                                __next_error('error reading file "%s" - %s' % (fname, nfo.error))

                                totalSummary[TS_WITH_ERRORS].value += 1

                                # захерачим файл в статистику без параметров
                                self.tvStats.store.append(destNode,
                                    (fname, '?', '?', '?', '?', None, None, None,
                                     self.iconErrors,
                                     markup_escape_text('Error: %s' % nfo.error),
                                     ))
                            else:
                                # статистика по sampleRate
                                if nfo.sampleRate in totalSampleRates:
                                    totalSampleRates[nfo.sampleRate].value += 1
                                else:
                                    totalSampleRates[nfo.sampleRate] = SummaryTableItem(1, None)

                                # статистика по bitsPerSample
                                if nfo.bitsPerSample in totalBitsPerSample:
                                    totalBitsPerSample[nfo.bitsPerSample].value += 1
                                else:
                                    totalBitsPerSample[nfo.bitsPerSample] = SummaryTableItem(1, None)

                                # прочая статистика
                                if nfo.lossy:
                                    totalSummary[TS_LOSSY].value += 1

                                for ixres, nres in enumerate(TS_BY_RES):
                                    if nfo.resolution == ixres:
                                        totalSummary[nres].value += 1

                                if nfo.missingTags:
                                    totalSummary[TS_MISTAGS].value += 1

                                #
                                self.progressAudioFiles += 1
                                self.labProgressAudioFiles.set_text(str(self.progressAudioFiles))

                                # захерачим файл в статистику
                                self.tvStats.store.append(destNode,
                                    (fname,
                                     disp_int_val_k(nfo.sampleRate),
                                     disp_int_val(nfo.channels),
                                     disp_int_val(nfo.bitsPerSample),
                                     disp_int_val(nfo.bitRate),
                                     disp_bool(nfo.lossy, self.iconLossyAudio),
                                     disp_bool(nfo.missingTags, self.iconMissingTags),
                                     __disp_resolution(nfo),
                                     disp_bool(bool(nfo.error), self.iconErrors),
                                     markup_escape_text(nfo.get_hint_str()),
                                     ))

                            dirinfo.update_from_file(nfo)

                    #
                    self.progressBar.pulse()
                    flush_gtk_events()

            dirinfo.flush()
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
            self.phase_start_page()
            return

        #
        # вроде как всё нормально - показываем статистику
        #

        def fill_summary_table(srcd, tv, tostr, _sort):
            """Заполнение Gtk.ListStore статистической таблицы.

            srcd    - словарь, где ключи - названия строк,
                      а значения - кортежи вида ('имя параметра', значение, Pixbuf);
                      последний элемент кортежа м.б. None,
                      если отображение иконок не требуется;
            tv      - экземпляр TreeViewShell;
            tostr   - функция, преобразующая значение параметра в строку;
            _sort   - булевское значение, True - сортировать таблицу по
                      именам параметров;
            icons   - булевское значение, True - последние элементы
                      кортежей в словаре srcd содержат экземпляры Pixbuf."""

            __pcts = lambda n: 0 if not self.progressAudioFiles else int(float(n) / self.progressAudioFiles * 100.0)
            __s_pcts = lambda n, p: '%d (%d%%)' % (n, p)

            tv.refresh_begin()

            dlst = srcd.items()
            if _sort:
                dlst = sorted(dlst)

            def __append_summary_table(param, sti):
                if sti.value:
                    pcts = __pcts(sti.value)

                    tv.store.append((tostr(param),
                        __s_pcts(sti.value, pcts),
                        pcts,
                        sti.icon))

            for param, sti in dlst:
                if param != 0:
                    __append_summary_table(param, sti)

            # сюда попадают файлы, где нет соотв. параметра в метаданных
            if 0 in srcd:
                __append_summary_table('?', srcd[0])

            tv.refresh_end()

        # заполняем таблицу sampleRates
        fill_summary_table(totalSampleRates, self.tvSampleRates, disp_int_val_k, True)

        # заполняем таблицу bitsPerSample
        fill_summary_table(totalBitsPerSample, self.tvBitsPerSample, disp_int_val, True)

        # заполняем прочую статистику
        fill_summary_table(totalSummary, self.tvSummary, str, False)

        #
        self.phase_result()

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

    def fcStartDir_current_folder_changed(self, fc):
        self.cfg.lastDirectory = self.fcStartDir.get_current_folder()
        print('Search directory changed to "%s"' % self.cfg.lastDirectory)

    def phase_start_page(self):
        self.phase = self.PHASE_START_PAGE

        self.fcStartDir.set_current_folder(self.cfg.lastDirectory)

        self.stopScanning = True

        self.btnRun.set_label('Start')

        self.boxStartSettings.set_sensitive(True)

        self.boxFileCtls.set_visible(False)
        self.boxFileCtls.set_sensitive(False)

        self.boxProgress.set_visible(False)
        self.boxProgress.set_sensitive(False)

        self.pages.set_current_page(self.PAGE_START)

    def phase_start_scan(self):
        self.phase = self.PHASE_SCANNING

        self.stopScanning = False
        self.btnRun.set_label('Stop')

        self.boxStartSettings.set_sensitive(False)

        self.boxFileCtls.set_visible(False)
        self.boxFileCtls.set_sensitive(False)

        self.boxProgress.set_visible(True)
        self.boxProgress.set_sensitive(True)

        self.pages.set_current_page(self.PAGE_START)
        self.scan_statistics()

    def phase_result(self):
        self.phase = self.PHASE_RESULT

        self.btnRun.set_label('Scan other directory')

        self.boxProgress.set_visible(False)
        self.boxProgress.set_sensitive(False)

        self.boxFileCtls.set_sensitive(True)
        self.boxFileCtls.set_visible(True)

        self.pages.set_current_page(self.PAGE_RESULT)

    def phaseSwitchingWidget_clicked(self, wgt):
        if self.phase == self.PHASE_START_PAGE:
            # нажата кнопка "Start"
            self.phase_start_scan()
        elif self.phase == self.PHASE_SCANNING:
            # нажата кнопка "Stop"
            self.phase_start_page()
        else:
            # нажата кнопка "Scan other directory"
            self.phase_start_page()

    def handle_unhandled(self, exc_type, exc_value, exc_traceback):
        # дабы не зациклиться, если че рухнет в этом обработчике
        sys.excepthook = sys.__excepthook__

        msg = '%s: %s' % (exc_type.__name__, str(exc_value))

        print('** %s' % msg, file=sys.stderr)
        print_exception(exc_type, exc_value, exc_traceback)

        msg_dialog(self.window, 'Unhandled exception', msg)

        sys.exit(255)

    def run(self):
        sys.excepthook = self.handle_unhandled
        Gtk.main()


if __name__ == '__main__':
    MainWnd().run()
