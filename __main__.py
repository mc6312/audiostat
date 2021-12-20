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


from gtktools import *
from gi.repository import Gtk#, Gdk, GObject, Pango, GLib
#from gi.repository.GdkPixbuf import Pixbuf

from traceback import print_exception
from warnings import warn

from audiostat import *


class MainWnd():
    PAGE_START, PAGE_PROGRESS, PAGE_STATS = range(3)

    # столбцы TreeModel дерева статистики
    STC_NAME, STC_SAMPLERATE, STC_CHANNELS, STC_BITSPERSAMPLE, STC_BITRATE, STC_LOSSY, STC_MISSINGTAGS = range(7)

    def wnd_destroy(self, widget, data=None):
        #!!!
        self.stopScanning = True
        Gtk.main_quit()

    def __init__(self):
        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'audiostat.ui')

        self.window = uibldr.get_object('wndMain')

        labTitle, labSubTitle = get_ui_widgets(uibldr,
            'labTitle', 'labSubTitle')

        self.window.set_title(TITLE_VERSION)
        labTitle.set_text(TITLE)
        labSubTitle.set_text(VERSION)

        isize = 128 #!!!
        self.window.set_icon(resldr.load_pixbuf('images/audiostat.svg',
            isize, isize))

        self.warningIcon = load_system_icon('dialog-warning', Gtk.IconSize.MENU, False, symbolic=True)

        #
        self.pages, self.btnRun = get_ui_widgets(uibldr,
            'pages', 'btnRun')

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
        swStats.set_min_content_height(WIDGET_BASE_HEIGHT * 24)
        swStats.set_size_request(-1, WIDGET_BASE_HEIGHT * 24)

        self.tvStats = TreeViewShell.new_from_uibuilder(uibldr, 'tvStats')
        self.tvStats.view.set_size_request(WIDGET_BASE_WIDTH * 96, -1)

        self.tvSummary = TreeViewShell.new_from_uibuilder(uibldr, 'tvSummary')

        #
        #TODO сделать загрузку/сохранение текущих параметров
        self.fcStartDir.set_current_folder(os.path.expanduser('~'))
        self.entFileTypes.set_text(' '.join(sorted(AUDIO_FILE_TYPES)))

        #
        self.stopScanning = False
        self.progressFiles = 0
        self.progressAudioFiles = 0
        self.progressErrors = 0

        self.__go_to_start_page()

        self.window.show_all()
        uibldr.connect_signals(self)

    def scan_statistics(self):
        self.stopScanning = False
        self.progressFiles = 0
        self.progressAudioFiles = 0
        self.progressErrors = 0

        def __scan_directory(destNode, fdir):
            """Обход подкаталога.

            Параметры:
                destNode    - Gtk.TreeIter,
                fdir        - строка, каталог.

            Возвращает кортеж трёх элементов:
                1й:         количество аудиофайлов и подкаталогов в каталоге;
                2й и 3й:    экземпляры AudioFileInfo с минимальными
                            и максимальными параметрами найденных файлов."""

            dirNFiles = 0

            dirMinInfo = AudioFileInfo()
            # !!!
            dirMinInfo.sampleRate = 100000000
            dirMinInfo.channels = 16384
            dirMinInfo.bitsPerSample = 1024
            dirMinInfo.bitRate = 1000000000

            dirMaxInfo = AudioFileInfo()

            self.labProgressPath.set_text(fdir)
            print('Scanning "%s"' % fdir, file=sys.stderr)

            def __next_error(msg):
                print(msg, file=sys.stderr)

                self.progressErrors += 1
                self.labProgressErrors.set_text(str(self.progressErrors))

            def __int_val_k(i):
                return '?' if not i else '%.1f' % (i / 1000.0)

            def __int_val(i):
                return '?' if not i else str(i)

            #TODO возможно, придётся как-то отслеживать выход за пределы fdir симлинками?
            for fname in os.listdir(fdir):
                if self.stopScanning:
                    return

                fpath = os.path.abspath(os.path.join(fdir, fname))

                if os.path.isdir(fpath):
                    # столбцы TreeStore:
                    # name, samplerate, channels, bitspersample, bitrate, lossy, missingtags
                    subNode = self.tvStats.store.append(destNode,
                        (fname, '', '', '', '', None, None))

                    subNFiles, subMinInfo, subMaxInfo = __scan_directory(subNode, fpath)

                    if not subNFiles:
                        # нафига нам пустые каталоги?
                        self.tvStats.store.remove(subNode)
                    else:
                        dirNFiles += 1

                        if dirMinInfo.sampleRate > subMinInfo.sampleRate:
                            dirMinInfo.sampleRate = subMinInfo.sampleRate

                        if dirMaxInfo.sampleRate < subMaxInfo.sampleRate:
                            dirMaxInfo.sampleRate = subMaxInfo.sampleRate

                        #TODO добавить проверки прочих полей
                        warn('добавить проверки прочих полей')

                        # дополняем запись прожёванного каталога
                        self.tvStats.store.set(subNode,
                            (self.STC_SAMPLERATE, self.STC_CHANNELS, self.STC_BITSPERSAMPLE, self.STC_BITRATE, self.STC_LOSSY, self.STC_MISSINGTAGS),
                            ('%s…%s' % (__int_val_k(subMinInfo.sampleRate), __int_val_k(subMaxInfo.sampleRate)),
                             '%s…%s' % (__int_val(subMinInfo.channels), __int_val(subMaxInfo.channels)),
                             '%s…%s' % (__int_val(subMinInfo.bitsPerSample), __int_val(subMaxInfo.bitsPerSample)),
                             '%s…%s' % (__int_val_k(subMinInfo.bitRate), __int_val_k(subMaxInfo.bitRate)),
                             None if not subMinInfo.lossy else self.warningIcon,
                             None if not subMinInfo.missingTags else self.warningIcon))
                else:
                    self.progressFiles += 1
                    self.labProgressFiles.set_text(str(self.progressFiles))

                    r = get_audio_file_info(fpath)

                    if r.error:
                        'error reading file "%s" - %s' % (fname, r.error)
                    elif r.isAudio:
                        dirNFiles += 1

                        if r.sampleRate < dirMinInfo.sampleRate:
                            dirMinInfo.sampleRate = r.sampleRate

                        if r.sampleRate > dirMaxInfo.sampleRate:
                            dirMaxInfo.sampleRate = r.sampleRate

                        #TODO добавить проверки прочих полей
                        warn('добавить проверки прочих полей')

                        self.progressAudioFiles += 1
                        self.labProgressAudioFiles.set_text(str(self.progressAudioFiles))

                        # захерачим файл в статистику
                        # столбцы TreeStore:
                        # name, samplerate, channels, bitspersample, bitrate, lossy, missingtags
                        self.tvStats.store.append(destNode,
                            (fname,
                             __int_val_k(r.sampleRate),
                             __int_val(r.channels),
                             __int_val(r.bitsPerSample),
                             __int_val_k(r.bitRate),
                             None if not r.lossy else self.warningIcon,
                             None if not r.missingTags else self.warningIcon))

                    #error, lossy, mime, sampleRate, channels, bitsPerSample, missingTags

                    #
                    self.progressBar.pulse()
                    flush_gtk_events()

            return (dirNFiles, dirMinInfo, dirMaxInfo)

        #
        # собираем статистику
        #
        try:
            self.tvStats.refresh_begin()

            _, totalMinInfo, totalMaxInfo = __scan_directory(None, self.fcStartDir.get_current_folder())

            self.tvStats.sortColumn = self.STC_NAME
            self.tvStats.refresh_end()
        except Exception as ex:
            print_exception(*sys.exc_info())
            es = 'Error: %s' % repr(ex)
            msg_dialog(self.window, 'Error', es)
            self.stopScanning = True
            self.__go_to_start_page()

        if self.stopScanning:
            self.__go_to_start_page()
            return

        #
        # вроде как всё нормально - показываем статистику
        #

        # заполняем итоговую таблицу
        def __add_summary(key, value):
            self.tvSummary.store.append((key, str(value)))

        self.tvSummary.refresh_begin()

        __add_summary('Total files found:', self.progressFiles)
        __add_summary('Audio files:', self.progressAudioFiles)
        #TODO добавить счётчики по метаданным
        __add_summary('Errors:', self.progressErrors)

        self.tvSummary.refresh_end()

        #
        self.btnRun.set_label('Scan other directory')
        self.pages.set_current_page(self.PAGE_STATS)

    def __go_to_start_page(self):
        self.pages.set_current_page(self.PAGE_START)
        self.btnRun.set_label('Start')

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

    def main(self):
        Gtk.main()


def main():
    MainWnd().main()

    return 0


if __name__ == '__main__':
    main()
