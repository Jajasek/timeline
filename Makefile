INSTALL_DIR=/usr

install:
	install -D src/lib/* -t ${DESTDIR}${INSTALL_DIR}/lib/timeline/
	sed -i "s/\TIMELINE_INSTALL_DIR/${INSTALL_DIR}" ${DESTDIR}${INSTALL_DIR}/lib/timeline/*
	mkdir -p ${DESTDIR}${INSTALL_DIR}/bin
	ln -s ../lib/timeline/timeline ${DESTDIR}${INSTALL_DIR}/bin/timeline
	install -D src/etc/timeline.conf -t ${DESTDIR}/etc/

