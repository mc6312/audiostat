packer = tar
pack = $(packer) -caf
unpack = $(packer) --keep-newer-files -xaf
arcx = .tar.xz
#
imagedir = ./images
backupdir = ~/shareddocs/pgm/python/
installdir = ~/bin
desktopfdir = ~/.local/share/applications
icondir = ~/.local/share/icons
distribdir = ~/downloads
#
basename = audiostat
srcversion = audiostat
version = $(shell python3 -c 'from $(srcversion) import VERSION; print(VERSION)')
branch = $(shell git symbolic-ref --short HEAD)
title_version = $(shell python3 -c 'from $(srcversion) import TITLE_VERSION; print(TITLE_VERSION)')
title = $(shell python3 -c 'from $(srcversion) import TITLE; print(TITLE)')
#
todo = TODO
docs = COPYING Changelog README.md $(todo)
zipname = $(basename).zip
arcname = $(basename)$(arcx)
srcarcname = $(basename)-$(branch)-src$(arcx)
pysrcs = *.py
uisrcs = *.ui
grsrcs = $(imagedir)/*.svg
srcs = $(pysrcs) $(uisrcs) $(grsrcs)
iconfn = $(basename).svg
desktopfn = $(basename).desktop
winiconfn = $(basename).ico
winiconsize = 128

app:
	zip $(zipname) $(srcs)
	python3 -m zipapp $(zipname) -o $(basename) -p "/usr/bin/env python3" -c
	rm $(zipname)

archive:
	make todo
	$(pack) $(srcarcname) $(srcs) Makefile *.geany $(docs)

distrib:
	make app
	make desktop
	make winiconfn
	make todo
	$(eval distname = $(basename)-$(version)$(arcx))
	$(pack) $(distname) $(basename) $(docs) $(desktopfn) $(winiconfn)
	mv $(distname) $(distribdir)

backup:
	make archive
	mv $(srcarcname) $(backupdir)

update:
	$(unpack) $(backupdir)$(srcarcname)

commit:
	make todo
	git commit -a -uno -m "$(version)"
	@echo "не забудь сказать git push"

show-branch:
	@echo "$(branch)"

docview:
	$(eval docname = README.htm)
	@echo "<html><head><meta charset="utf-8"><title>$(title_version) README</title></head><body>" >$(docname)
	markdown_py README.md >>$(docname)
	@echo "</body></html>" >>$(docname)
	x-www-browser $(docname)
	#rm $(docname)

todo:
	pytodo.py $(pysrcs) >$(todo)

desktop:
	@echo "[Desktop Entry]" >$(desktopfn)
	@echo "Name=$(title)" >>$(desktopfn)
	@echo "Exec=/usr/bin/env python3 $(shell realpath $(installdir)/$(basename))" >>$(desktopfn)
	@echo "Icon=$(shell realpath $(icondir)/$(iconfn))" >>$(desktopfn)
	@echo "Type=Application" >>$(desktopfn)
	@echo "StartupWMClass=$(basename)" >>$(desktopfn)
	@echo "Categories=Multimedia;Utilites" >>$(desktopfn)

winiconfn:
	convert -background transparent -density 600x600 -resize $(winiconsize)x$(winiconsize) $(imagedir)/$(iconfn) $(winiconfn)

install:
	make app
	cp $(basename) $(installdir)/
	cp $(imagedir)/$(iconfn) $(icondir)/
	make desktop
	cp $(desktopfn) $(desktopfdir)/

uninstall:
	rm $(desktopfdir)/$(desktopfn)
	rm $(installdir)/$(basename)
	rm $(icondir)/$(iconfn)
