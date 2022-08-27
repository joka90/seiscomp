FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update \
   && apt install -y \
     build-essential \
     git \
     libboost-all-dev \
     libxml2-dev \
     flex \
     libfl-dev \
     libssl-dev \
     libcrypto++-dev \
     python3-dev \
     python3-numpy \
     qtbase5-dev \
     libqt5svg5-dev \
     libmysqlclient-dev \
     libpq-dev \
     libsqlite3-dev \
     libbson-dev \
     libmseed-dev \
     ca-certificates \
     gawk \
     libncurses-dev \
     devscripts equivs dpkg-dev \
     curl zstd file bison texinfo flex python3 nscd libgmp3-dev libmpc-dev libmpfr-dev \
     ed libpcre2-dev cmake pkg-config libexpat1-dev time libtinfo-dev \
   && \
     rm -rf /var/lib/apt/lists/*

COPY clone.sh /usr/bin/clone.sh

