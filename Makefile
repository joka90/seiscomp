default: all

all:
	mkdir -p build
	cd build && ccmake ../ -DCMAKE_INSTALL_PREFIX=${HOME}/seiscomp
	echo "*** To build the sources change into the 'build' directory and enter make[ install] ***"


docker-img:
	docker build -t seiscomp-build .

docker-run:
	docker run -v $(PWD)/build:/tmp/build -it seiscomp-build /bin/bash
