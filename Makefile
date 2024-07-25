install:
	mkdir ${DESTDIR}/usr/local/lib/timeline
	shopt -s extglob
	cp src/!(timeline.conf) ${DESTDIR}/usr/local/lib/timeline/
	ln -s ../lib/timeline/timeline ${DESTDIR}/usr/local/bin/timeline
	cp src/timeline.conf ${DESTDIR}/etc/

