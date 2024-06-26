BLENDER_VERSION?=3.2
BLENDER_ARCHIVE?=blender-$(BLENDER_VERSION).2-linux-x64.tar.xz
PYTHON_VERSION?=3.10
CC3_VERSION?=1_1_6

BLENDER_DIR?=build/blender
BLENDER?=$(BLENDER_DIR)/blender

.PHONY: fix_format

fix_format:
	black .

release:
	-rm blenderset.zip
	zip -r blenderset.zip blenderset

interactive:
	PWD=$(shell pwd) $(BLENDER) blank.blend

vinterspel:
	$(BLENDER) /home/hakan/src/lightning_crowd/vinterspel2021/vinterspelen_bkg.blend

delfinensynth:
	$(BLENDER) delfinensynth.blend

run: run-run

run-%:
	$(BLENDER) -b --python $*.py

run-cuda:
	$(BLENDER) -b --python run.py -- --cycles-device CUDA

run-optix:
	$(BLENDER) -b --python run.py -- --cycles-device OPTIX

run-forever-%:
	while true; do $(MAKE) run-$*; sleep 1; done

import_animations:
	$(BLENDER) -b --python import_animation.py

.PHONY: sync_env

sync_env:
	pip install -r requirements/misc.txt

build/downloads/Python-$(PYTHON_VERSION).0.tar.xz:
	wget -O $@ https://www.python.org/ftp/python/$(PYTHON_VERSION).0/Python-$(PYTHON_VERSION).0.tar.xz

build/downloads/$(BLENDER_ARCHIVE):
	wget -O $@ https://mirrors.dotsrc.org/blender/release/Blender$(BLENDER_VERSION)/$(BLENDER_ARCHIVE)

build/downloads/cc3_blender_tools-$(CC3_VERSION).zip:
	wget -O $@ https://github.com/soupday/cc3_blender_tools/archive/refs/tags/$(CC3_VERSION).zip

build/downloads/%:
	@echo $@ must be downloaded manually
	@exit 1

build/downloads:
	-mkdir -p $@

build/downloads/_envoy: build/downloads build/downloads/$(BLENDER_ARCHIVE) build/downloads/cc3_blender_tools-$(CC3_VERSION).zip build/downloads/Python-$(PYTHON_VERSION).0.tar.xz
	@touch $@

# TODO: Consider pointing blender to a config that is local to this project
$(BLENDER_DIR)/_envoy: build/downloads/_envoy
	rm -rf $(@D) || :
	mkdir -p $(@D)
	tar \
		--no-same-permissions \
		--no-same-owner \
		--strip 1 \
		-xf $(<D)/$(BLENDER_ARCHIVE)  -C $(@D)
	tar \
		--no-same-permissions \
		--no-same-owner \
		-xf $(<D)/Python-$(PYTHON_VERSION).0.tar.xz  -C $(@D) Python-$(PYTHON_VERSION).0/Include/
	# Converting blender environment to venv...
	mv $(@D)/Python-$(PYTHON_VERSION).0/Include/*.h $(@D)/$(BLENDER_VERSION)/python/include/python$(PYTHON_VERSION)/
	-mkdir $(@D)/$(BLENDER_VERSION)/python/include/python$(PYTHON_VERSION)/cpython/
	mv $(@D)/Python-$(PYTHON_VERSION).0/Include/cpython/*.h $(@D)/$(BLENDER_VERSION)/python/include/python$(PYTHON_VERSION)/cpython/
	mv $(@D)/$(BLENDER_VERSION)/python $(@D)/$(BLENDER_VERSION)/python.bak
	$(@D)/$(BLENDER_VERSION)/python.bak/bin/python$(PYTHON_VERSION) -m venv --prompt blender $(@D)/$(BLENDER_VERSION)/python
	rsync -rv $(@D)/$(BLENDER_VERSION)/python.bak/lib/ $(@D)/$(BLENDER_VERSION)/python/lib/
	rsync -rv $(@D)/$(BLENDER_VERSION)/python.bak/include/ $(@D)/$(BLENDER_VERSION)/python/include/
	# Installing first-party addon...
	ln -s `pwd`/blenderset $(@D)/$(BLENDER_VERSION)/scripts/addons/
	# Installing third-party addons...
	unzip $(<D)/cc3_blender_tools-$(CC3_VERSION).zip -d $(@D)/$(BLENDER_VERSION)/scripts/addons/
	# Remember to enable addons using the blender GUI
	ln -s $(BLENDER_VERSION) $(@D)/current
	@touch $@

constraints.txt: $(wildcard requirements/*.txt)
	pip-compile --strip-extras --allow-unsafe --output-file $@ $^ $(SILENT)

docker-build:
	docker build -t blenderset .

docker-run: docker-run-run
k8s-run: k8s-run-run

ASSETS_DIR=$(shell python -c 'import json, pathlib; print(json.load(open(pathlib.Path.home() / ".config/blenderset/config.json")).get("assets_dir", "../blenderset-assets"))')
METADATA_DIR=$(shell python -c 'import json, pathlib; print(json.load(open(pathlib.Path.home() / ".config/blenderset/config.json")).get("metadata_dir", pathlib.Path.cwd().parent / "blenderset-metadata"))')
RENDERS_DIR=$(shell python -c 'import json, pathlib; print(json.load(open(pathlib.Path.home() / ".config/blenderset/config.json")).get("renders_dir", pathlib.Path.cwd() / "renders"))')
docker-run-%:
	docker  run --rm --privileged --gpus all -v /dev:/dev  -ti -u `id -u` \
			-v $(ASSETS_DIR):/blenderset-assets \
			-v $(METADATA_DIR):/blenderset-metadata/ \
			-v $(RENDERS_DIR):/workdir/renders \
            blenderset make run-enable_addons run-$*

TORCHX_GPU?=GTX1080
TORCHX_REPLICAS?=4
torchx-run-%:
	torchx run --scheduler kubernetes utils.sh -h $(TORCHX_GPU) --num_replicas $(TORCHX_REPLICAS) \
				--mounts type=bind,src=$(ASSETS_DIR),dst=/blenderset-assets,readonly,type=bind,src=$(RENDERS_DIR),dst=/workdir/renders,type=bind,src=$(METADATA_DIR),dst=/blenderset-metadata \
				make run-enable_addons run-$*
