# FROM nvidia/cudagl:10.1-base-ubuntu18.04
# FROM nvidia/cuda:12.3.1-runtime-ubuntu20.04
FROM nvidia/cuda:11.6.1-runtime-ubuntu20.04

# Enviorment variables
ENV DEBIAN_FRONTEND noninteractive
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

# Install dependencies
RUN apt-get update && apt-get install -y \
	wget \
	libopenexr-dev \
	bzip2 \
	build-essential \
	zlib1g-dev \
	libxmu-dev \
	libxi-dev \
	libxxf86vm-dev \
	libfontconfig1 \
	libxrender1 \
	libgl1-mesa-glx \
	xz-utils \
    rsync unzip python3-pip \
    libjpeg62-dev libavcodec-dev libswscale-dev libffi-dev \
    libjack-jackd2-0 libpulse0 libxkbcommon0

# Set the working directory
RUN mkdir /workdir
WORKDIR /workdir

# Insall blender and other dependencier
COPY requirements /workdir/requirements/
COPY Makefile init_env.sh constraints.txt enable_addons.py /workdir/
RUN mkdir /workdir/custom_addons/
COPY custom_addons/* /workdir/custom_addons/

RUN sh ./init_env.sh
RUN chmod -R 777 /workdir/build/blender/current/scripts/addons/cc_blender_tools*

# Set up home dir
RUN mkdir /home/home
RUN chmod 777 /home/home
ENV HOME /home/home

# Install blenderset
COPY blenderset /workdir/blenderset/
COPY run.py blank.blend /workdir/
