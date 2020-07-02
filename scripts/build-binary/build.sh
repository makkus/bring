#!/usr/bin/env bash

DEFAULT_PYTHON_VERSION="3.7.7"
DEFAULT_PYINSTALLER_VERSION="3.6"

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

function command_exists {
   type "$1" > /dev/null 2>&1 ;
}

if ! command_exists realpath; then

  function realpath() {

      local _X="$PWD"
      local _LNK=$1
      cd "$(dirname "$_LNK")"
      if [ -h "$_LNK" ]; then
          _LNK="$(readlink "$_LNK")"
          cd "$(dirname "$_LNK")"
      fi
      echo "$PWD/$(basename "$_LNK")"
      cd "$_X"

  }
fi

function prepare () {

    local build_dir="${1}"
    local venv_name="${2}"
    local python_version="${3}"
    local pyinstaller_version="${4}"
    local requirements_file="${5}"
    local project_root="${6}"
    local output_dir="${7}"

    mkdir -p "${build_dir}"

    echo "checking dependencies"
    ensure_dependencies "${python_version}" "${venv_name}"
    echo " -> dependencies all good"
    echo

    local venv_path="${HOME}/.pyenv/versions/${venv_name}"
    if [ -n "${venv_name}" ] && [ -n "${requirements_file}" ]; then
      echo "preparing build"
      install_requirements "${venv_path}" "${requirements_file}" "${pyinstaller_version}"
    fi

    source "${venv_path}/bin/activate"

    pip install -U --extra-index-url https://pkgs.frkl.io/frkl/dev "${project_root}[all]"

    mkdir -p "${output_dir}"

}


function ensure_dependencies () {

    local python_version="${1}"
    local venv_name="${2}"

    export PATH="${HOME}/.pyenv/bin:$PATH"

    # pyenv
    if ! command_exists pyenv; then

        if command_exists curl; then
            curl https://pyenv.run | bash
        elif command_exists wget; then
            wget -O- https://pyenv.run | bash
        else
            echo "Can't install pyenv. Need wget or curl."
            exit 1
        fi

        eval "$(pyenv init -)"
        eval "$(pyenv virtualenv-init -)"

    fi

    if [ -n "${python_version}" ]; then
      # python version
      local python_path="${HOME}/.pyenv/versions/${python_version}"
      if [ ! -e "${python_path}" ]; then
          env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install "${python_version}"
      fi
    fi

    if [ -n "${venv_name}" ]; then
      # virtualenv
      local virtualenv_path="${HOME}/.pyenv/versions/${venv_name}"
      if [ ! -e "${virtualenv_path}" ]; then
          pyenv virtualenv "${python_version}" "${venv_name}"
      fi
    fi

}


function install_requirements () {

    local venv_path="${1}"
    local requirements_file="${2}"
    local pyinstaller_version="${3}"

    source "${venv_path}/bin/activate"

    echo "installing dependencies from: ${requirements_file}"

    pip install -U pip
    pip install setuptools==44.0.0
    pip install -U pp-ez
    pip install "pyinstaller==${pyinstaller_version}"

    pip install -U --extra-index-url https://pkgs.frkl.io/frkl/dev -r "${requirements_file}"

    deactivate

    echo " --> dependencies installed"

}


function build_artifact () {

    local project_root="${1}"
    local build_dir="${2}"
    local venv_path="${3}"
    local output_dir="${4}"
    local os_type="${5}"
    local spec_file="${6}"

    local target="${output_dir}/${os_type}"

    echo "building package"

    source "${venv_path}/bin/activate"

    local temp_dir="${build_dir}/build-${RANDOM}"

    mkdir -p "${temp_dir}"

    cd "${project_root}"

    pyinstaller --clean -y --dist "${target}" --workpath "${temp_dir}" "${spec_file}"

    rm -rf "${temp_dir}"

    deactivate

    echo "  -> package built"

}


function main () {

    local project_root="${1}"
    local build_dir="${2}"
    local venv_name="${3}"
    local python_version="${4}"
    local pyinstaller_version="${5}"
    local requirements_file="${6}"
    local output_dir="${7}"
    local spec_file="${8}"

    # activate pyenv if already installed
    if [ -f "$HOME/.pyenv/.pyenvrc" ]; then
      source "$HOME/.pyenv/.pyenvrc"
    fi

    if [ -z "${DOCKER_BUILD}" ]; then
        DOCKER_BUILD=false
    fi

    local venv_path="${HOME}/.pyenv/versions/${venv_name}"

    if [ -f /.dockerenv ]; then

           prepare "${build_dir}" "${venv_name}" "${python_version}" "${pyinstaller_version}" "${requirements_file}" "${project_root}" "${output_dir}"
           source "${venv_path}/bin/activate"
           build_artifact "${project_root}" "${build_dir}" "${venv_path}" "${output_dir}" "${OS_TYPE}" "${spec_file}"

    else

        if [ "$DOCKER_BUILD" = true ]; then

            docker run -v "${THIS_DIR}/..:/src/" registry.gitlab.com/freckles-io/freckles-build "${entrypoint}"
#            docker run -v "${THIS_DIR}/../:/src/" freckles-build-debian

        else

            prepare "${build_dir}" "${venv_name}" "${python_version}" "${pyinstaller_version}" "${requirements_file}" "${project_root}" "${output_dir}"
            build_artifact "${project_root}" "${build_dir}" "${venv_path}" "${output_dir}" "${OSTYPE}" "${spec_file}"

        fi

    fi
}

while [[ -n "$1" ]]; do
  case "$1" in
  --project-root)
    shift
    PROJECT_ROOT="${1}"
    ;;
  --build-dir)
    shift
    BUILD_DIR="${1}"
    ;;
  --python-version)
    shift
    PYTHON_VERSION="${1}"
    ;;
  --pyinstaller-version)
    shift
    PYINSTALLER_VERSION="${1}"
    ;;
  --requirements)
    shift
    REQUIREMENTS_FILE="${1}"
    ;;
  --output-dir)
    shift
    OUTPUT_DIR="${1}"
    ;;
  --spec-file)
    shift
    SPEC_FILE="${1}"
    ;;
  --venv-name)
    shift
    VENV_NAME="${1}"
    ;;
  --)
    shift
    break
    ;;
  -*|--*=) # unsupported flags
    echo "Error: Invalid argument '${1}'" >&2
    exit 1
    ;;
  esac
  shift
done

echo

if [ -z "${PROJECT_ROOT}" ]
then
   PROJECT_ROOT=$(pwd)
fi
if [ ! -d "${PROJECT_ROOT}" ]
then
  echo "project root '${PROJECT_ROOT} does not exist or is not directory"
  exit 1
fi
PROJECT_ROOT=$(realpath "${PROJECT_ROOT}")

if [ -z "${BUILD_DIR}" ]
then
  BUILD_DIR="/tmp"
fi
mkdir -p ${BUILD_DIR}
if [ ! -d "${BUILD_DIR}" ]
then
  echo "can't create build dir '${BUILD_DIR}"
  exit 1
fi
BUILD_DIR=$(realpath "${BUILD_DIR}")

if [ -z "${VENV_NAME}" ]
then
  VENV_NAME=$(basename "${PROJECT_ROOT}-build")
fi

if [ -z "${PYTHON_VERSION}" ]
then
  PYTHON_VERSION="${DEFAULT_PYTHON_VERSION}"
fi

if [ -z "${PYINSTALLER_VERSION}" ]
then
  PYINSTALLER_VERSION="${DEFAULT_PYINSTALLER_VERSION}"
fi

if [ -z "${REQUIREMENTS_FILE}" ]
then
  REQUIREMENTS_FILE="${PROJECT_ROOT}/ci/build-binary/requirements-build.txt"
fi
if [ ! -f "${REQUIREMENTS_FILE}" ]
then
  echo "requirements file '${REQUIREMENTS_FILE} does not exist"
  exit 1
fi
REQUIREMENTS_FILE=$(realpath "${REQUIREMENTS_FILE}")

if [ -z "${OUTPUT_DIR}" ]
then
  OUTPUT_DIR="${PROJECT_ROOT}/dist"
fi
mkdir -p ${OUTPUT_DIR}
if [ ! -d "${OUTPUT_DIR}" ]
then
  echo "can't create output dir '${OUTPUT_DIR}"
  exit 1
fi
OUTPUT_DIR=$(realpath "${OUTPUT_DIR}")

if [ -z ${SPEC_FILE} ]
then
  SPEC_FILE="${PROJECT_ROOT}/scripts/build-binary/onefile.spec"
fi
if [ ! -f "${SPEC_FILE}" ]
then
  echo "spec file '${SPEC_FILE} does not exist"
  exit 1
fi
SPEC_FILE=$(realpath "$SPEC_FILE")

echo "project root: ${PROJECT_ROOT}"
echo "requirements file: ${REQUIREMENTS_FILE}"
echo "spec file: ${SPEC_FILE}"
echo "output dir: ${OUTPUT_DIR}"
echo "build dir: ${BUILD_DIR}"
echo "venv name: ${VENV_NAME}"
echo "python version: ${PYTHON_VERSION}"
echo "pyinstaller version: ${PYINSTALLER_VERSION}"

echo
echo "starting build..."
echo

set -e
set -x

main "${PROJECT_ROOT}" "${BUILD_DIR}" "${VENV_NAME}" "${PYTHON_VERSION}" "${PYINSTALLER_VERSION}" "${REQUIREMENTS_FILE}" "${OUTPUT_DIR}" "${SPEC_FILE}"

set +e
set +x

echo
echo "build finished"
echo
