install:
#	mkdir ${DESTDIR}/usr/local/lib/timeline
	install src/* ${DESTDIR}/usr/local/lib/timeline/
	rm ${DESTDIR}/usr/local/lib/timeline/timeline.conf
	ln -s ../lib/timeline/timeline ${DESTDIR}/usr/local/bin/timeline
	install src/timeline.conf ${DESTDIR}/etc/

