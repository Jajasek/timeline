install:
	mkdir -p ${DESTDIR}/usr/local/lib/timeline
	install src/filter-in-terminal-tab src/filter.py src/link.py src/list.py src/nvim.config.config src/traverser.py ${DESTDIR}/usr/local/lib/timeline/
	mkdir -p ${DESTDIR}/usr/local/bin
	ln -s ../lib/timeline/timeline ${DESTDIR}/usr/local/bin/timeline
	mkdir -p ${DESTDIR}/etc
	install src/timeline.conf ${DESTDIR}/etc/

