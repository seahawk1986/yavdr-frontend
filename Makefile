all:
	$(MAKE) -C tools/

install:
	$(MAKE) -C tools/ DESTDIR=$(DESTDIR) install

clean:
	$(MAKE) -C tools/ clean
