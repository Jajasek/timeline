install:
#	mkdir ${DESTDIR}/usr/local/lib/timeline
	install -D src/* ${DESTDIR}/usr/local/lib/timeline/
	rm ${DESTDIR}/usr/local/lib/timeline/timeline.conf
	mkdir -p ${DESTDIR}/usr/local/bin
	ln -s ../lib/timeline/timeline ${DESTDIR}/usr/local/bin/timeline
	install -D src/timeline.conf ${DESTDIR}/etc/

