install:
#	mkdir ${DESTDIR}/usr/local/lib/timeline
	shopt -s extglob
	install src/!(timeline.conf) ${DESTDIR}/usr/local/lib/timeline/
	ln -s ../lib/timeline/timeline ${DESTDIR}/usr/local/bin/timeline
	install src/timeline.conf ${DESTDIR}/etc/

