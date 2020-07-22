#!/usr/bin/env bash
#
#
#   .----------------.  .----------------.  .----------------.  .----------------.
#  | .--------------. || .--------------. || .--------------. || .--------------. |
#  | |  _________   | || |  _______     | || |  ___  ____   | || |   _____      | |
#  | | |_   ___  |  | || | |_   __ \    | || | |_  ||_  _|  | || |  |_   _|     | |
#  | |   | |_  \_|  | || |   | |__) |   | || |   | |_/ /    | || |    | |       | |
#  | |   |  _|      | || |   |  __ /    | || |   |  __'.    | || |    | |   _   | |
#  | |  _| |_       | || |  _| |  \ \_  | || |  _| |  \ \_  | || |   _| |__/ |  | |
#  | | |_____|      | || | |____| |___| | || | |____||____| | || |  |________|  | | .sh
#  | |              | || |              | || |              | || |              | |
#  | '--------------' || '--------------' || '--------------' || '--------------' |
#   '----------------'  '----------------'  '----------------'  '----------------'
#
#                                                                          version: 0.1
#
#                                                   Copyright 2020 by Markus Binsteiner
#                              Licensed under The Parity Public License (version 7.0.0)
#
# ----------------------------------------------------------------------------------------------------------------------
#
# Generic one-shot wrapper script for single-file executables.
#
# The main purpose of this script is as a 'curly' bootstrap script, hosted on 'https://frkl.sh' or a custom domain:
#
#     curl https://frkl.sh | bash [<arguments>]
#
# or
#
#     wget -O- https://frkl.sh | bash [<arguments>]
#
# It is recommended that, if you want to use this to bootstrap your own application (or a 3rd party one, in order to
# have more control), you host this script yourself on your own infrastructure.
#
# If called like above without arguments, this will download the executable in question, put it in
# $HOME/.local/share/frkl/bin and add a few lines of init code to .profile/.zprofile/.bash_profile
# so the binary is on PATH.
#
# If called with argument, e.g. for the 'frecklecute' application, it is used like so:
#
#     curl https://freckles.sh | bash -s -- frecklecute -t admin@freckles.io user-exists admin
#
# This will execute the last portion of the command as if 'frecklecute' was installed locally. In this
# case this script will not do any of the 'install' tasks from the scenario above, it will only store the executable itself
# under '$HOME/.local/share/frkl/bin' in order to be able to re-use it.
#
#
# For more information please visit:
#
#    https://gitlab.com/frkl/frkl.sh
#
#
# Environment variables to control this scripts behaviour
# -------------------------------------------------------
#
# CLEANUP=false
#
#     Whether to remove the application from the system after execution.
#
#     This deletes the $FRKL_BASE_DIR folder (default: $HOME/.local/share/frkl). It will not remove the init code
#     in any of the init files if exists (see: $ADD_TO_INIT documentation), nor any links to the installed binaries.
#
# UPDATE=false
#
#     Re-downloads the executable, even if it already exists.
#
# SILENT=false
#
#     Don't output any messages (still outputs errors).
#
# VERSION=stable
#
#     The channel out of which to download the executable, either 'stable', or 'dev'.
#
# ADD_TO_INIT=default
#
#     Add code to one or several (init) files so freckles and its apps are in $PATH.
#
#     If the value equals 'default', it will make sure the init code is in $HOME/.profile, and, if they exist, also in
#     $HOME/.bash_profile and $HOME/.zprofile.
#
#     If set to a ":"-delimited string, all of the items in that list will be used instead, and created if they don't
#     exist.
#
# NO_ADD_TO_INIT=false
#
#     Prevents adding init code to any files (even if 'ADD_TO_INIT' is set).
#
# FRKL_BASE_DIR=$HOME/.local/share/freckles
#
#     The (base) directory to be used for the 'freckles' install.
#
# FRKL_BIN_DIR=$HOME/.local/share/freckles/bin
#
#     The directory where to put executable files. This directory will be added to PATH for the values in $ADD_TO_INIT.
#
# FRKL_INSTALL_NAME='freckles'
#
#     The name of the (main) executable. Don't change that unless you are me (or you know what you are doing).
#
# FRKL_EXECUTABLE_ALIASES="frecklecute"
#
#     ":"-delimited string of all the aliases 'freckles' can be called. Don't change unless you know what you are doing.
#
# FRKL_NO_LOG=false
#     Disable writing logs to a file.
#
# FRKL_DOWNLOAD_URL_LINUX=https://dl.frkl.io/linux-gnu/freckles
#
#     Download url for the linux (x64_86) binary.
#
# FRKL_DOWNLOAD_URL_DARWIN=https://dl.frkl.io/darwin/freckles
#
#     Download url for the Mac OS X (x64_86) binary.
#
# FRKL_HIDE_CURSOR=true
#
#     Whether to hide/show the cursor while freck is running.
#
# FRKL_DEBUG=false
#
#     Enable debugging for this script. You (hopefully) don't need this.
#


# =========================================================
# CONSTANTS

# required

COOKIECUTTER_PROJECT_NAME="bring"

#
if [[ -n "${APP_NAME}" ]]; then
  PROJECT_NAME="${APP_NAME}"
#
elif [[ "${COOKIECUTTER_PROJECT_NAME}" != "{{ cookiecutter.exe_name }}" ]]; then
#
  PROJECT_NAME="${COOKIECUTTER_PROJECT_NAME}"
fi

DEFAULT_LINUX_DOWNLOAD_URL="https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/${PROJECT_NAME}"
DEFAULT_DARWIN_DOWNLOAD_URL="https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/darwin/${PROJECT_NAME}"

DEV_LINUX_DOWNLOAD_URL="https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/${PROJECT_NAME}"
DEV_DARWIN_DOWNLOAD_URL="https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/darwin/${PROJECT_NAME}"

FRKL_INSTALL_NAME="${PROJECT_NAME}"
FRKL_EXECUTABLE_ALIASES="${PROJECT_NAME}"

# changeable

# name of directory under ~/.local/share and ~/.cache
FRKL_SHARE_DIR_NAME="frkl"

# directory where the executable will be put
# FRKL_BIN_DIR="${HOME}/.local/share/frkl/bin"


# =========================================================
# Utility functions

# ---------------------------------------------------------------
# Logs string(s) to file.
#
# Arguments:
#   $@: content to log
#
# Globals:
#   $FRKL_NO_LOG: whether to log or not to log
#   $FRKL_LOG_FILE: where to log (parent directory must exist
#
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_log {
    if [ "${DEBUG}" = true ]; then
        (>&2 echo "debug: $*")
    fi
    if ! [ "$FRKL_NO_LOG" = true ]; then
        echo "... $*" >> "$FRKL_LOG_FILE"
    fi
}

# ---------------------------------------------------------------
# Print message(s) to user.
#
# Arguments:
#   $@: content to print
#
# Globals:
#   $SILENT: whether to disable output
#
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_output {
    _frkl_log "$@"

    if ! [ "${SILENT}" = true ]; then
        echo "$@"
    fi
}

# ---------------------------------------------------------------
# Print error message(s) to user.
#
# Arguments:
#   $@: content to print
#
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_error_output {

    _frkl_log "ERROR: ${1}"
    printf "\r"
    (>&2 echo "$@")
}

# ---------------------------------------------------------------
# Print error message and exit execution.
#
# Arguments:
#   $1: error message (optional)
#
# Globals:
#   $PROGNAME: the name of this script
#   $FRKL_NO_LOG: whether to log to file or not
#   $FRKL_LOG_FILE: the path to the log file
# ---------------------------------------------------------------
function _frkl_error_exit {

    if [ -z "${PROGNAME}" ]; then
        local p_name=""
    else
        local p_name="${PROGNAME}: "
    fi

    if ! [ "$FRKL_NO_LOG" = true ]; then
        _frkl_error_output "${p_name}${1:-"Unknown Error"}, check log file for details -> $FRKL_LOG_FILE"
    else
        _frkl_error_output "${p_name}${1:-"Unknown Error"}, re-run with log enabled for details"
    fi
    _frkl_show_cursor
    exit 1
}

# ---------------------------------------------------------------
# Checks whether a command exists in any of the relevant paths.
#
# Arguments:
#   $1: the command to check
#
# Globals:
#   PATH: the (global)
#   FRKL_BIN_DIR: the path to where to install the executable
#   LOCAL_LINK_PATH: the path to where to link the installed executable
#
# Returns:
#   whether the command exists (0) or not (1) (return code)
# ---------------------------------------------------------------
function _frkl_command_exists {
    PATH="$PATH:$LOCAL_LINK_PATH:$FRKL_BIN_DIR" type "$1" > /dev/null 2>&1 ;
}

# ---------------------------------------------------------------
# Checks whether a command exists in ~/.local/share/frkl/bin.
#
# Arguments:
#   $1: the command to check
#
# Globals:
#   PATH: the (global)
#   FRKL_BIN_DIR: the path to where to install the executable
#
# Returns:
#   whether the command exists (0) or not (1) (return code)
# ---------------------------------------------------------------
function _frkl_command_exists_frkl {
    PATH="$FRKL_BIN_DIR" type "$1" > /dev/null 2>&1 ;
}

# ---------------------------------------------------------------
# Shows the cursor.
# ---------------------------------------------------------------
function _frkl_show_cursor {
    if _frkl_command_exists tput; then
        tput cnorm
    fi
}

# ---------------------------------------------------------------
# Hides the cursor.
# ---------------------------------------------------------------
function _frkl_hide_cursor {
    if _frkl_command_exists tput && [ "$FRKL_HIDE_CURSOR" = true ]; then
        tput civis
    fi
}


# ---------------------------------------------------------------
# Executes a command and logs it's output to the log file.
#
# Arguments:
#   $@: command, incl. arguments, last token is a message to be displayed in case of error
#
# Globals:
#   $FRKL_NO_LOG: whether to log or not
#   $FRKL_LOG_FILE: the path to the log file
#
# ---------------------------------------------------------------
function _frkl_execute_log {

    # shellcheck disable=SC2124
    local error="${@: -1}"
    if ! [ "$FRKL_NO_LOG" = true ]; then
        _frkl_log "executing: " "${@:1:$#-1}"
        ("${@:1:$#-1}" >> "$FRKL_LOG_FILE" 2>&1) || _frkl_error_exit "$error"
    else
        ("${@:1:$#-1}" >> /dev/null 2>&1) || _frkl_error_exit "$error"
    fi

}

# ---------------------------------------------------------------
# Download a file.
#
# This tries to figure out whether either the 'wget' or 'curl'
# executable exist, and use the first one it finds to download
# the requested file.
#
# Arguments:
#   $1: the url to download
#   $2: the target file name
# ---------------------------------------------------------------
function _frkl_download {

    local tmp_dir
    tmp_dir=$(mktemp -d -t _frkl_XXXXXXXXXXXXX)
    local tmp_file
    tmp_file="${tmp_dir}/_download"

    if _frkl_command_exists wget; then
        _frkl_execute_log wget -O "${tmp_file}" "$1" "Could not download $1 using wget"
    elif _frkl_command_exists curl; then
        _frkl_execute_log curl -o "${tmp_file}" "$1" "Could not download $1 using curl"
    else
        _frkl_error_output "Could not find 'wget' nor 'curl' to download files. Exiting..."
        rm -rf "${tmp_dir}"
        return 1
    fi

    _frkl_execute_log mv "${tmp_file}" "${2}"  "Could not move downloaded file to: ${2}"
    rm -rf "${tmp_dir}"

    return 0
}


# ---------------------------------------------------------------
# Calculates a relative path between two files/folders.
#
# from: https://unix.stackexchang .com/questions/85060/getting-relative-links-between-two-paths
# both $1 and $2 are absolute paths beginning with /
# $1 must be a canonical path; that is none of its directory
# components may be ".", ".." or a symbolic link
#
# Arguments:
#   $1: source path
#   $2: target path
# Returns:
#   the relative path to $2/$target from $1/$source# Arguments:
# ---------------------------------------------------------------
function _frkl_calculate_relative_path {

    local source=$1
    local target=$2

    local common_part=$source
    result=""

    while [ "${target#"$common_part"}" = "$target" ]; do
        # no match, means that candidate common part is not correct
        # go up one level (reduce common part)
        common_part=$(dirname "$common_part")
        # and record that we went back, with correct / handling
        if [ -z "$result" ]; then
            result=".."
        else
            result="../$result"
        fi
    done

    if [ "$common_part" = / ]; then
        # special case for root (no common path)
        result="$result/"
    fi

    # since we now have identified the common part,
    # compute the non-common part
    forward_part="${target#"$common_part"}"

    # and now stick all parts together
    if [ -n "$result" ] && [ -n "$forward_part" ]; then
        result="$result$forward_part"
    elif [ -n "$forward_part" ]; then
        # extra slash removal
        result="${forward_part#?}"
    fi

    printf '%s\n' "$result"

}

# ---------------------------------------------------------------
# Link a file into a folder, creating that folder if necessary
#
# Arguments:
#   $1: target folder
#   $2: file name
#   $3: link folder
#   $4: link name
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_link_path {

    local target_folder="$1"
    local target_name="$2"
    local link_folder="$3"
    local link_name="$4"

    mkdir -p "$link_folder"
    rm -f "$link_folder/$link_name"

    relpath="$(_frkl_calculate_relative_path "$link_folder" "$target_folder")"

    if [ -z "${relpath}" ]; then
        local full_target=${target_name}
    else
        local full_target="${relpath}/${target_name}"
    fi

    _frkl_log "linking $link_folder/$link_name to $full_target"

    ln -s "$full_target" "$link_folder/$link_name"

}

# ---------------------------------------------------------------
# Show a spinner while running a long running task.
#
# from: https://unix.stackexchange.com/questions/225179/display-spinner-while-waiting-for-some-process-to-finish
#
# Arguments:
#   $1: the pid of the process to watch
#   $2: the message to display
# Globals:
#   None
# ---------------------------------------------------------------
function _frkl_show_spinner {

    local -r pid="${1}"
    local -r msg="${2}"
    local -r delay='0.1'
    local spinstr='\|/-'
    local temp

    while ps a | awk '{print $1}' | grep -q "${pid}"; do
        temp="${spinstr#?}"

        full_msg="[${spinstr:0:1}] ${msg}"

        if _frkl_command_exists tput; then
            columns=$(tput cols)
        else
            columns=45
        fi

        # escape in case of templating
        len=${#full_msg}
        #

        if [ "$len" -lt "${columns}" ]; then
            full=${full_msg}
        else
            if [ $columns -ge 6 ]; then
                columns2=$((columns - 4))
                full="${full_msg:0:${columns2}}..."
            else
                full=${full_msg:0:${columns}}
            fi
        fi


        back=${full//?/\\b}

        #shellcheck disable=SC2059
        printf "$full"

        spinstr=${temp}${spinstr%"${temp}"}
        sleep "${delay}"
        #shellcheck disable=SC2059
        printf "$back"
    done
    erase=${full//?/\ }
    #shellcheck disable=SC2059
    printf "$erase"
    echo -en "\r"

    wait "${pid}"

}

# --------------------------------------------------------------
# Executes a command and displays a spinner while it is running.
# Arguments:
#   $@: command, incl. arguments, second to last token is the user message, last token is a message to be displayed
#       in case of error
#
# Globals:
#   $FRKL_NO_LOG: whether to log or not
#   $LOG_FILE: the path to the log file
#
# --------------------------------------------------------------
function _frkl_run_with_spinner {

    # shellcheck disable=SC2124
    local msg="${@: -1}"
    # shellcheck disable=SC2124
    local error="${@:(-2):1}"

    # TODO: check whether 'ps' command is available

    if ! [ "${SILENT}" = true ]; then

        if ! [ "$FRKL_NO_LOG" = true ]; then
            ("${@:1:$#-2}" >> "$FRKL_LOG_FILE" 2>&1 || _frkl_error_exit "$error") &
            if _frkl_show_spinner "$!" "$msg"; then
                return 0
            else
                return 1
            fi
        else
            ("${@:1:$#-2}" >> /dev/null 2>&1 || _frkl_error_exit "$error") &
            if _frkl_show_spinner "$!" "$msg"; then
                return 0
            else
                return 1
            fi
        fi

    else
        # shellcheck disable=SC2068
        _frkl_execute_log ${@:1:$#-2} "$error"
    fi

}

# ---------------------------------------------------------------
# Calculates the executable to download, depending on the platform.
#
# Arguments:
#   None
#
# Globals:
#   FRKL_DOWNLOAD_URL_LINUX: url for Linux
#   FRKL_DOWNLOAD_URL_DARWIN: url for Mac OS X
#
# Returns:
#
# ---------------------------------------------------------------
function _frkl_calculate_url {

    # figure out which os we are running
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        download_url="$FRKL_DOWNLOAD_URL_LINUX"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        download_url="$FRKL_DOWNLOAD_URL_DARWIN"
    elif [[ "$OSTYPE" == "cygwin" ]]; then
        # POSIX compatibility layer and Linux environment emulation for Windows
        _frkl_error_output "Sorry, Cygwin platform is not supported (at the moment, anyway). Exiting..."
        exit 6
    elif [[ "$OSTYPE" == "msys" ]]; then
        # Lightweight shell and GNU utilities compiled for Windows (part of MinGW)
        _frkl_error_output "Sorry, msys/MinGW platform is not supported (at the moment, anyway). Exiting..."
        exit 6
    elif [[ "$OSTYPE" == "win32" ]]; then
        _frkl_error_output "Sorry, win32 platform is not supported (at the moment, anyway). Exiting..."
        exit 6
    elif [[ "$OSTYPE" == "freebsd"* ]]; then
        _frkl_error_output "Sorry, freebsd platform is not supported (at the moment, anyway). Exiting..."
        exit 6
    else
        _frkl_error_output "Could not figure out which platform I'm running on. Exiting..."
        exit 6
    fi

    printf '%s\n' "$download_url"

}


# =========================================================
# main functions

# ---------------------------------------------------------------
# Initialize (global) variables.
#
# Arguments:
#   $@: arguments provided to script itself
#
# Globals:
#   $FRKL_DEBUG: whether enable debug output
#   $FRKL_BASE_DIR: the base dir for installation
#   $FRKL_BIN_DIR: the directory to install the executable into
#   $FRKL_DOWNLOAD_URL_LINUX: download url for linux
#   $FRKL_DOWNLOAD_URL_DARWIN: download url for Mac OS X
#
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_init_vars {

    if [ "$FRKL_DEBUG" = true ]; then
        set -x
    fi

    # determine whether we run with sudo, or not
    if [ "$EUID" != 0 ]; then
        # root_permissions=false
        FRKL_INSTALL_USER="$USER"
    else
        # root_permissions=true
        if [ -z "$SUDO_USER" ]; then
            if [ -n "$USER" ]; then
                FRKL_INSTALL_USER="$USER"
            else
                FRKL_INSTALL_USER="root"
            fi
        else
            FRKL_INSTALL_USER="$SUDO_USER"
        fi
    fi

    FRKL_INSTALL_GROUP=$(id -ng "${FRKL_INSTALL_USER}")
    FRKL_INSTALL_USER_HOME="$(eval echo "~$FRKL_INSTALL_USER")"

    if [ -z "$FRKL_BASE_DIR" ]; then
        FRKL_BASE_DIR="${FRKL_INSTALL_USER_HOME}/.local/share/${FRKL_SHARE_DIR_NAME}"
    fi

    FRKL_CACHE_DIR="${FRKL_INSTALL_USER_HOME}/.cache/${FRKL_SHARE_DIR_NAME}"

    if [ -z "$FRKL_BIN_DIR" ]; then
        FRKL_BIN_DIR="${FRKL_BASE_DIR}/bin"
    fi

    if [ -z "$VERSION" ]; then
        FRKL_VERSION="stable"
    else
        FRKL_VERSION="$VERSION"
    fi

    FRKL_INSTALL_PATH="$FRKL_BIN_DIR/$FRKL_INSTALL_NAME"

    FRKL_INSTALL_LOG_DIR="${FRKL_BASE_DIR}/logs"
    FRKL_LOG_FILE="${FRKL_INSTALL_LOG_DIR}/install_$(date +"%Y%m%d%H%M%S").log"

    if [ -n "$1" ]; then
        FRKL_EXECUTABLE_NAME=$(basename "$1")
    else
        FRKL_EXECUTABLE_NAME="__FRKL_EXE_NOT_SET__"
    fi

    if [ -z "$FRKL_DOWNLOAD_URL_LINUX" ]; then
        if [[ "$FRKL_VERSION" == "dev" ]]; then
            FRKL_DOWNLOAD_URL_LINUX="${DEV_LINUX_DOWNLOAD_URL}"
        else
            FRKL_DOWNLOAD_URL_LINUX="${DEFAULT_LINUX_DOWNLOAD_URL}"
        fi
    fi
    if [ -z "$FRKL_DOWNLOAD_URL_DARWIN" ]; then
        if [[ "$FRKL_VERSION" == "dev" ]]; then
            FRKL_DOWNLOAD_URL_DARWIN="${DEV_DARWIN_DOWNLOAD_URL}"
        else
            FRKL_DOWNLOAD_URL_DARWIN="${DEFAULT_DARWIN_DOWNLOAD_URL}"
        fi
    fi

    #    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    #        FRKL_INSTALL_PLATFORM="Linux"
    #    elif [[ "$OSTYPE" == "darwin"* ]]; then
    #        FRKL_INSTALL_PLATFORM="Mac OS X"
    #    else
    #        FRKL_INSTALL_PLATFORM="Unsupported"
    #    fi

    if [ "$NO_ADD_TO_INIT" = true ]; then
        ADD_TO_INIT=""
    else
        if [ -z "$ADD_TO_INIT" ]; then
            ADD_TO_INIT="default"
        fi
    fi

    if [ -z "$FRKL_HIDE_CURSOR" ]; then
        FRKL_HIDE_CURSOR="true"
    fi

}

# ---------------------------------------------------------------
# Sets up necessary folders and files.
#
# Arguments:
#   None
#
# Globals:
#   $FRKL_BASE_DIR: the base dir for installation
#   $FRKL_INSTALL_USER: the user to install for
#   $FRKL_INSTALL_GROUP: the users group
#   $FRKL_LINK_BIN_PATH: an optional directory to link the executable into
#   $FRKL_NO_LOG: whether to log to a file or not
#   $INSTALL_LOG_DIR: the directory that contains the logs
#   $FRKL_LOG_FILE: the path to the log file
#
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_init_directories {

    mkdir -p "$FRKL_BASE_DIR"
    chown "$FRKL_INSTALL_USER:$FRKL_INSTALL_GROUP" "$FRKL_BASE_DIR"
    chmod 700 "$FRKL_BASE_DIR"

    mkdir -p "$FRKL_BIN_DIR"
    chown "$FRKL_INSTALL_USER:$FRKL_INSTALL_GROUP" "$FRKL_BIN_DIR"

    if [ -n "$FRKL_LINK_BIN_PATH" ]; then
        mkdir -p "$FRKL_LINK_BIN_PATH"
    fi

    if [ ! "$FRKL_NO_LOG" = true ]; then
        mkdir -p "$FRKL_INSTALL_LOG_DIR"
        touch "$FRKL_LOG_FILE"
        chmod 700 "$FRKL_LOG_FILE"
        chown "$FRKL_INSTALL_USER:$FRKL_INSTALL_GROUP" "$FRKL_INSTALL_LOG_DIR"
        rm -f "$FRKL_INSTALL_LOG_DIR/install.log"
        ln -s "$FRKL_LOG_FILE" "$FRKL_INSTALL_LOG_DIR/install.log"
    fi

}

# ---------------------------------------------------------------
# Linking the executable(s) to ${LOCAL_LINK_PATH}.
#
# Arguments:
#   $1: the name of the link
#   $2: target folder
#   $3: whether to be silent about it (default: false)
#
# ---------------------------------------------------------------
function _frkl_link_executable {

    local link_name=${1}
    local target_folder=${2}
    local no_output=${3}

    if [ -z "$target_folder" ]; then
        target_folder="$HOME/.local/bin"
    fi
    _frkl_execute_log mkdir -p "${target_folder}" "Could not create folder: ${target_folder}"

    local full_link_path="${target_folder}/${link_name}"
    if [ ! -e "${full_link_path}" ]; then

        local exe
        exe=$(PATH="$FRKL_BIN_DIR" type -p ${FRKL_INSTALL_NAME})

        exe_dir=$(dirname "${exe}")
        _frkl_link_path "${exe_dir}" "${FRKL_INSTALL_NAME}" "${target_folder}" "${link_name}"
        if [ ! "$no_output" = true ]; then
            _frkl_output "- linked executable from: ${full_link_path}"
        fi
    fi

}

# ---------------------------------------------------------------
# Add the bin path ot a bash/zsh init file.
#
# Arguments:
#   $1: path to init file
#   $2: whether to create the file if it doesn't exist (default: false)
#
# ---------------------------------------------------------------
function _frkl_add_to_init_file {

    local path=${1}
    local create=${2}

    if [ ! -e "${path}" ] && [ ! "${create}" = true ]; then
        return 1
    fi

    if ! grep -q '# begin: frkl init' "${path}"  > /dev/null 2>&1 ; then
        # shellcheck disable=SC2129
        echo "" >> "${path}"
        echo "# begin: frkl init" >> "${path}"
        echo "export FRKL_PATH=${FRKL_BIN_DIR}" >> "${path}"
        cat <<"EOF" >> "${path}"
if [ -d "$FRKL_PATH" ]; then
    PATH="$PATH:$FRKL_PATH"
fi
# end: frkl init
EOF
        _frkl_output "- added init section to: ${path}"
    fi
    return 0
}


# ---------------------------------------------------------------
# Bootstrapping the executable.
#
# If so chosen, this will create links into ${LOCAL_LINK_PATH}, as
# well as add that directory to $PATH, if not already present.
#
# Arguments:
#   $1: whether to install the application (true), or just place it under ~/.local/share/frkl (or whatever else is configured)
#
# Returns:
#   None
# ---------------------------------------------------------------
function _frkl_bootstrap {

    _frkl_init_directories
    if ! _frkl_command_exists_frkl $FRKL_INSTALL_NAME || [ "${1}" = true ]; then
        echo
    fi

    if ! _frkl_command_exists_frkl $FRKL_INSTALL_NAME || [ "${UPDATE}" = true ]; then
        url=$(_frkl_calculate_url)

        if ! _frkl_run_with_spinner _frkl_download "${url}" "${FRKL_INSTALL_PATH}" "Error downloading ${url}" "downloading ${url}"; then
            _frkl_error_exit "Error downloading ${url}"
        fi
        _frkl_output "- downloaded ${FRKL_INSTALL_NAME}: ${FRKL_INSTALL_PATH}"
        chown "${FRKL_INSTALL_USER}":"${FRKL_INSTALL_USER_GROUP}" "${FRKL_INSTALL_PATH}"
        chmod +x "${FRKL_INSTALL_PATH}"
    fi

    if [ "${1}" = true ]; then

        for alias in ${FRKL_EXECUTABLE_ALIASES//:/ }; do
            _frkl_link_executable "${alias}" "${FRKL_BIN_DIR}" "true"
        done

        # link to $HOME/.local/bin or similar
        if [ -n "${LOCAL_LINK_PATH}" ]; then
            _frkl_link_executable "${FRKL_INSTALL_NAME}" "${LOCAL_LINK_PATH}"

            for alias in ${FRKL_EXECUTABLE_ALIASES//:/ }; do
                _frkl_link_executable "${alias}" "${LOCAL_LINK_PATH}"
            done
        fi

        if [ ! "$NO_ADD_TO_INIT" = true ] && [[ "$FRKL_EXECUTABLE_NAME" == "__FRKL_EXE_NOT_SET__" ]]; then
            if [[ "$ADD_TO_INIT" == "default" ]]; then
                _frkl_add_to_init_file "$FRKL_INSTALL_USER_HOME/.profile" "true"
                _frkl_add_to_init_file "$FRKL_INSTALL_USER_HOME/.bash_profile" "false"
                _frkl_add_to_init_file "$FRKL_INSTALL_USER_HOME/.zprofile" "false"
            else
                for init_file in ${ADD_TO_INIT//:/ }; do
                    _frkl_add_to_init_file ${init_file} "true"
                done
            fi
        fi
    fi

}

# ---------------------------------------------------------------
# The main function.
# ---------------------------------------------------------------
function _frkl_main {

    # shellcheck disable=SC2068
    _frkl_init_vars ${@}

    # only continue if the command is a known alias (or no command)
    if [[ ":${FRKL_INSTALL_NAME}:${FRKL_EXECUTABLE_ALIASES}:__FRKL_EXE_NOT_SET__:" != *":${FRKL_EXECUTABLE_NAME}:"* ]]; then
        _frkl_error_exit "Executable '${FRKL_EXECUTABLE_NAME}' not supported. Exiting..."
        exit 1
    fi

    _frkl_hide_cursor
    trap '_frkl_error_exit "Bootstrapping interrupted, exiting..."' SIGHUP SIGINT SIGTERM

    # bootstrap, if command is not available
    if [ "${UPDATE}" = true ]; then
        rm -f "${FRKL_BIN_DIR}/{$FRKL_INSTALL_NAME}"
    fi
    if ! _frkl_command_exists_frkl $FRKL_INSTALL_NAME || [ "${UPDATE}" = true ] || [[ "$FRKL_EXECUTABLE_NAME" == "__FRKL_EXE_NOT_SET__" ]]; then
        _frkl_bootstrap true
        echo
    fi

    # only execute if command is provided, otherwise install in $FRKL_LINK_BIN_PATH
    if [[ "$FRKL_EXECUTABLE_NAME" == "__FRKL_EXE_NOT_SET__" ]]; then
        _frkl_output "No command provided, doing nothing. You might have to execute ' source ~/.profile' in order to have the installed executable(s) in your PATH."
        _frkl_show_cursor
        return 0
    else
        shift
        _frkl_log "Running executable: ${FRKL_INSTALL_NAME}"
        _frkl_log "   -> as: ${FRKL_EXECUTABLE_NAME}"
        _frkl_log "   -> with arguments: ${*}"
        PATH="$LOCAL_LINK_PATH:$FRKL_BIN_DIR:$PATH" f_ex="${FRKL_EXECUTABLE_NAME}" "${FRKL_BIN_DIR}/${FRKL_INSTALL_NAME}" "$@"
        exit_code=$?
        if [ "$CLEANUP" = true ]; then
            FRKL_NO_LOG=true
            rm -rf "$FRKL_BASE_DIR"
            _frkl_output "- deleted folder: ${FRKL_BASE_DIR}"
            rm -rf "$FRKL_CACHE_DIR"
            _frkl_output "- deleted cache: ${FRKL_CACHE_DIR}"
        fi
        _frkl_show_cursor
        return ${exit_code}
    fi
    _frkl_show_cursor

}


# ============================
# script execution entry point
# ============================

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Error: Could not determine app name."
  exit 1
fi

# adding PREFIX_COMMAND if necessary
if [ -z "${PREFIX_COMMAND}" ]; then
    PREFIX_COMMAND=()

fi

for arg in "$@"; do
    PREFIX_COMMAND+=("${arg}")
done


if ! (return 0 2>/dev/null); then


    # script is executed
    # shellcheck disable=SC2128
    if [[ "$BASH_SOURCE" == "" ]]; then
        #        FRKL_RUN_TYPE="pipe"
        _frkl_main "${PREFIX_COMMAND[@]}"
        exit $?
    else
        #        FRKL_RUN_TYPE="run"
        _frkl_main "${PREFIX_COMMAND[@]}"
        exit $?
    fi
else
    #     FRKL_RUN_TYPE="source"
    _frkl_init_vars "${PREFIX_COMMAND[@]}"
    #     ( _frkl_main "${PREFIX_COMMAND[@]}" )
    if [[ ":${PATH}:" != *":${FRKL_BIN_DIR}:"* ]]; then
        export PATH="$FRKL_BIN_DIR:$PATH"
    fi
fi
