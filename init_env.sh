# Initialize development environment
#
# Use like `. ./init_env.sh`.
#
# Note that venv will be created in current working directory as opposed to the
# directory in which this script resides.

PIP_CONSTRAINT=`pwd`/constraints.txt
export PIP_CONSTRAINT

mkdir -p build/downloads
if make build/blender/_envoy; then
  . build/blender/current/python/bin/activate
  pip install pip
  pip install --no-binary OpenEXR OpenEXR
fi
