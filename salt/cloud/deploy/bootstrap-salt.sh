#!/bin/sh -
#======================================================================================================================
# vim: softtabstop=4 shiftwidth=4 expandtab fenc=utf-8 spell spelllang=en cc=120
#======================================================================================================================
#
#          FILE: bootstrap-salt.sh
#
#   DESCRIPTION: Bootstrap Salt installation for various systems/distributions
#
#          BUGS: https://github.com/saltstack/salt-bootstrap/issues
#
#     COPYRIGHT: (c) 2012-2017 by the SaltStack Team, see AUTHORS.rst for more
#                details.
#
#       LICENSE: Apache 2.0
#  ORGANIZATION: SaltStack (saltstack.com)
#       CREATED: 10/15/2012 09:49:37 PM WEST
#======================================================================================================================
set -o nounset                              # Treat unset variables as an error

__ScriptVersion="2017.12.13"
__ScriptName="bootstrap-salt.sh"

__ScriptFullName="$0"
__ScriptArgs="$*"

#======================================================================================================================
#  Environment variables taken into account.
#----------------------------------------------------------------------------------------------------------------------
#   * BS_COLORS:                If 0 disables colour support
#   * BS_PIP_ALLOWED:           If 1 enable pip based installations(if needed)
#   * BS_PIP_ALL:               If 1 enable all python packages to be installed via pip instead of apt, requires setting virtualenv
#   * BS_VIRTUALENV_DIR:        The virtualenv to install salt into (shouldn't exist yet)
#   * BS_ECHO_DEBUG:            If 1 enable debug echo which can also be set by -D
#   * BS_SALT_ETC_DIR:          Defaults to /etc/salt (Only tweak'able on git based installations)
#   * BS_SALT_CACHE_DIR:        Defaults to /var/cache/salt (Only tweak'able on git based installations)
#   * BS_KEEP_TEMP_FILES:       If 1, don't move temporary files, instead copy them
#   * BS_FORCE_OVERWRITE:       Force overriding copied files(config, init.d, etc)
#   * BS_UPGRADE_SYS:           If 1 and an option, upgrade system. Default 0.
#   * BS_GENTOO_USE_BINHOST:    If 1 add `--getbinpkg` to gentoo's emerge
#   * BS_SALT_MASTER_ADDRESS:   The IP or DNS name of the salt-master the minion should connect to
#   * BS_SALT_GIT_CHECKOUT_DIR: The directory where to clone Salt on git installations
#======================================================================================================================


#======================================================================================================================
#  LET THE BLACK MAGIC BEGIN!!!!
#======================================================================================================================

# Bootstrap script truth values
BS_TRUE=1
BS_FALSE=0

# Default sleep time used when waiting for daemons to start, restart and checking for these running
__DEFAULT_SLEEP=3

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __detect_color_support
#   DESCRIPTION:  Try to detect color support.
#----------------------------------------------------------------------------------------------------------------------
_COLORS=${BS_COLORS:-$(tput colors 2>/dev/null || echo 0)}
__detect_color_support() {
    if [ $? -eq 0 ] && [ "$_COLORS" -gt 2 ]; then
        RC="\033[1;31m"
        GC="\033[1;32m"
        BC="\033[1;34m"
        YC="\033[1;33m"
        EC="\033[0m"
    else
        RC=""
        GC=""
        BC=""
        YC=""
        EC=""
    fi
}
__detect_color_support


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoerr
#   DESCRIPTION:  Echo errors to stderr.
#----------------------------------------------------------------------------------------------------------------------
echoerror() {
    printf "${RC} * ERROR${EC}: %s\n" "$@" 1>&2;
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echoinfo
#   DESCRIPTION:  Echo information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echoinfo() {
    printf "${GC} *  INFO${EC}: %s\n" "$@";
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echowarn
#   DESCRIPTION:  Echo warning informations to stdout.
#----------------------------------------------------------------------------------------------------------------------
echowarn() {
    printf "${YC} *  WARN${EC}: %s\n" "$@";
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  echodebug
#   DESCRIPTION:  Echo debug information to stdout.
#----------------------------------------------------------------------------------------------------------------------
echodebug() {
    if [ "$_ECHO_DEBUG" -eq $BS_TRUE ]; then
        printf "${BC} * DEBUG${EC}: %s\n" "$@";
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_command_exists
#   DESCRIPTION:  Check if a command exists.
#----------------------------------------------------------------------------------------------------------------------
__check_command_exists() {
    command -v "$1" > /dev/null 2>&1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_pip_allowed
#   DESCRIPTION:  Simple function to let the users know that -P needs to be used.
#----------------------------------------------------------------------------------------------------------------------
__check_pip_allowed() {
    if [ $# -eq 1 ]; then
        _PIP_ALLOWED_ERROR_MSG=$1
    else
        _PIP_ALLOWED_ERROR_MSG="pip based installations were not allowed. Retry using '-P'"
    fi

    if [ "$_PIP_ALLOWED" -eq $BS_FALSE ]; then
        echoerror "$_PIP_ALLOWED_ERROR_MSG"
        __usage
        exit 1
    fi
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __check_config_dir
#  DESCRIPTION:  Checks the config directory, retrieves URLs if provided.
#----------------------------------------------------------------------------------------------------------------------
__check_config_dir() {
    CC_DIR_NAME="$1"
    CC_DIR_BASE=$(basename "${CC_DIR_NAME}")

    case "$CC_DIR_NAME" in
        http://*|https://*)
            __fetch_url "/tmp/${CC_DIR_BASE}" "${CC_DIR_NAME}"
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        ftp://*)
            __fetch_url "/tmp/${CC_DIR_BASE}" "${CC_DIR_NAME}"
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        *://*)
            echoerror "Unsupported URI scheme for $CC_DIR_NAME"
            echo "null"
            return
            ;;
        *)
            if [ ! -e "${CC_DIR_NAME}" ]; then
                echoerror "The configuration directory or archive $CC_DIR_NAME does not exist."
                echo "null"
                return
            fi
            ;;
    esac

    case "$CC_DIR_NAME" in
        *.tgz|*.tar.gz)
            tar -zxf "${CC_DIR_NAME}" -C /tmp
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tgz")
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tar.gz")
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        *.tbz|*.tar.bz2)
            tar -xjf "${CC_DIR_NAME}" -C /tmp
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tbz")
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tar.bz2")
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
        *.txz|*.tar.xz)
            tar -xJf "${CC_DIR_NAME}" -C /tmp
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".txz")
            CC_DIR_BASE=$(basename "${CC_DIR_BASE}" ".tar.xz")
            CC_DIR_NAME="/tmp/${CC_DIR_BASE}"
            ;;
    esac

    echo "${CC_DIR_NAME}"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __check_unparsed_options
#  DESCRIPTION:  Checks the placed after the install arguments
#----------------------------------------------------------------------------------------------------------------------
__check_unparsed_options() {
    shellopts="$1"
    # grep alternative for SunOS
    if [ -f /usr/xpg4/bin/grep ]; then
        grep='/usr/xpg4/bin/grep'
    else
        grep='grep'
    fi
    unparsed_options=$( echo "$shellopts" | ${grep} -E '(^|[[:space:]])[-]+[[:alnum:]]' )
    if [ "$unparsed_options" != "" ]; then
        __usage
        echo
        echoerror "options are only allowed before install arguments"
        echo
        exit 1
    fi
}


#----------------------------------------------------------------------------------------------------------------------
#  Handle command line arguments
#----------------------------------------------------------------------------------------------------------------------
_KEEP_TEMP_FILES=${BS_KEEP_TEMP_FILES:-$BS_FALSE}
_TEMP_CONFIG_DIR="null"
_SALTSTACK_REPO_URL="https://github.com/saltstack/salt.git"
_SALT_REPO_URL=${_SALTSTACK_REPO_URL}
_DOWNSTREAM_PKG_REPO=$BS_FALSE
_TEMP_KEYS_DIR="null"
_SLEEP="${__DEFAULT_SLEEP}"
_INSTALL_MASTER=$BS_FALSE
_INSTALL_SYNDIC=$BS_FALSE
_INSTALL_MINION=$BS_TRUE
_INSTALL_CLOUD=$BS_FALSE
_VIRTUALENV_DIR=${BS_VIRTUALENV_DIR:-"null"}
_START_DAEMONS=$BS_TRUE
_DISABLE_SALT_CHECKS=$BS_FALSE
_ECHO_DEBUG=${BS_ECHO_DEBUG:-$BS_FALSE}
_CONFIG_ONLY=$BS_FALSE
_PIP_ALLOWED=${BS_PIP_ALLOWED:-$BS_FALSE}
_PIP_ALL=${BS_PIP_ALL:-$BS_FALSE}
_SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/etc/salt}
_SALT_CACHE_DIR=${BS_SALT_CACHE_DIR:-/var/cache/salt}
_PKI_DIR=${_SALT_ETC_DIR}/pki
_FORCE_OVERWRITE=${BS_FORCE_OVERWRITE:-$BS_FALSE}
_GENTOO_USE_BINHOST=${BS_GENTOO_USE_BINHOST:-$BS_FALSE}
_EPEL_REPO=${BS_EPEL_REPO:-epel}
_EPEL_REPOS_INSTALLED=$BS_FALSE
_UPGRADE_SYS=${BS_UPGRADE_SYS:-$BS_FALSE}
_INSECURE_DL=${BS_INSECURE_DL:-$BS_FALSE}
_CURL_ARGS=${BS_CURL_ARGS:-}
_FETCH_ARGS=${BS_FETCH_ARGS:-}
_GPG_ARGS=${BS_GPG_ARGS:-}
_WGET_ARGS=${BS_WGET_ARGS:-}
_ENABLE_EXTERNAL_ZMQ_REPOS=${BS_ENABLE_EXTERNAL_ZMQ_REPOS:-$BS_FALSE}
_SALT_MASTER_ADDRESS=${BS_SALT_MASTER_ADDRESS:-null}
_SALT_MINION_ID="null"
# _SIMPLIFY_VERSION is mostly used in Solaris based distributions
_SIMPLIFY_VERSION=$BS_TRUE
_LIBCLOUD_MIN_VERSION="0.14.0"
_EXTRA_PACKAGES=""
_HTTP_PROXY=""
_SALT_GIT_CHECKOUT_DIR=${BS_SALT_GIT_CHECKOUT_DIR:-/tmp/git/salt}
_NO_DEPS=$BS_FALSE
_FORCE_SHALLOW_CLONE=$BS_FALSE
_DISABLE_SSL=$BS_FALSE
_DISABLE_REPOS=$BS_FALSE
_CUSTOM_REPO_URL="null"
_CUSTOM_MASTER_CONFIG="null"
_CUSTOM_MINION_CONFIG="null"
_QUIET_GIT_INSTALLATION=$BS_FALSE
_REPO_URL="repo.saltstack.com"
_PY_EXE=""
_INSTALL_PY="$BS_FALSE"

# Defaults for install arguments
ITYPE="stable"


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __usage
#  DESCRIPTION:  Display usage information.
#----------------------------------------------------------------------------------------------------------------------
__usage() {
    cat << EOT

  Usage :  ${__ScriptName} [options] <install-type> [install-type-args]

  Installation types:
    - stable              Install latest stable release. This is the default
                          install type
    - stable [branch]     Install latest version on a branch. Only supported
                          for packages available at repo.saltstack.com
    - stable [version]    Install a specific version. Only supported for
                          packages available at repo.saltstack.com
    - daily               Ubuntu specific: configure SaltStack Daily PPA
    - testing             RHEL-family specific: configure EPEL testing repo
    - git                 Install from the head of the develop branch
    - git [ref]           Install from any git ref (such as a branch, tag, or
                          commit)

  Examples:
    - ${__ScriptName}
    - ${__ScriptName} stable
    - ${__ScriptName} stable 2016.3
    - ${__ScriptName} stable 2016.3.1
    - ${__ScriptName} daily
    - ${__ScriptName} testing
    - ${__ScriptName} git
    - ${__ScriptName} git 2016.3
    - ${__ScriptName} git v2016.3.1
    - ${__ScriptName} git 06f249901a2e2f1ed310d58ea3921a129f214358

  Options:
    -h  Display this message
    -v  Display script version
    -n  No colours
    -D  Show debug output
    -c  Temporary configuration directory
    -g  Salt Git repository URL. Default: ${_SALTSTACK_REPO_URL}
    -w  Install packages from downstream package repository rather than
        upstream, saltstack package repository. This is currently only
        implemented for SUSE.
    -k  Temporary directory holding the minion keys which will pre-seed
        the master.
    -s  Sleep time used when waiting for daemons to start, restart and when
        checking for the services running. Default: ${__DEFAULT_SLEEP}
    -L  Also install salt-cloud and required python-libcloud package
    -M  Also install salt-master
    -S  Also install salt-syndic
    -N  Do not install salt-minion
    -X  Do not start daemons after installation
    -d  Disables checking if Salt services are enabled to start on system boot.
        You can also do this by touching /tmp/disable_salt_checks on the target
        host. Default: \${BS_FALSE}
    -P  Allow pip based installations. On some distributions the required salt
        packages or its dependencies are not available as a package for that
        distribution. Using this flag allows the script to use pip as a last
        resort method. NOTE: This only works for functions which actually
        implement pip based installations.
    -U  If set, fully upgrade the system prior to bootstrapping Salt
    -I  If set, allow insecure connections while downloading any files. For
        example, pass '--no-check-certificate' to 'wget' or '--insecure' to
        'curl'. On Debian and Ubuntu, using this option with -U allows to obtain
        GnuPG archive keys insecurely if distro has changed release signatures.
    -F  Allow copied files to overwrite existing (config, init.d, etc)
    -K  If set, keep the temporary files in the temporary directories specified
        with -c and -k
    -C  Only run the configuration function. Implies -F (forced overwrite).
        To overwrite Master or Syndic configs, -M or -S, respectively, must
        also be specified. Salt installation will be ommitted, but some of the
        dependencies could be installed to write configuration with -j or -J.
    -A  Pass the salt-master DNS name or IP. This will be stored under
        \${BS_SALT_ETC_DIR}/minion.d/99-master-address.conf
    -i  Pass the salt-minion id. This will be stored under
        \${BS_SALT_ETC_DIR}/minion_id
    -p  Extra-package to install while installing Salt dependencies. One package
        per -p flag. You're responsible for providing the proper package name.
    -H  Use the specified HTTP proxy for all download URLs (including https://).
        For example: http://myproxy.example.com:3128
    -Z  Enable additional package repository for newer ZeroMQ
        (only available for RHEL/CentOS/Fedora/Ubuntu based distributions)
    -b  Assume that dependencies are already installed and software sources are
        set up. If git is selected, git tree is still checked out as dependency
        step.
    -f  Force shallow cloning for git installations.
        This may result in an "n/a" in the version number.
    -l  Disable ssl checks. When passed, switches "https" calls to "http" where
        possible.
    -V  Install Salt into virtualenv
        (only available for Ubuntu based distributions)
    -a  Pip install all Python pkg dependencies for Salt. Requires -V to install
        all pip pkgs into the virtualenv.
        (Only available for Ubuntu based distributions)
    -r  Disable all repository configuration performed by this script. This
        option assumes all necessary repository configuration is already present
        on the system.
    -R  Specify a custom repository URL. Assumes the custom repository URL
        points to a repository that mirrors Salt packages located at
        repo.saltstack.com. The option passed with -R replaces the
        "repo.saltstack.com". If -R is passed, -r is also set. Currently only
        works on CentOS/RHEL and Debian based distributions.
    -J  Replace the Master config file with data passed in as a JSON string. If
        a Master config file is found, a reasonable effort will be made to save
        the file with a ".bak" extension. If used in conjunction with -C or -F,
        no ".bak" file will be created as either of those options will force
        a complete overwrite of the file.
    -j  Replace the Minion config file with data passed in as a JSON string. If
        a Minion config file is found, a reasonable effort will be made to save
        the file with a ".bak" extension. If used in conjunction with -C or -F,
        no ".bak" file will be created as either of those options will force
        a complete overwrite of the file.
    -q  Quiet salt installation from git (setup.py install -q)
    -x  Changes the python version used to install a git version of salt. Currently
        this is considered experimental and has only been tested on Centos 6. This
        only works for git installations.
    -y  Installs a different python version on host. Currently this has only been
        tested with Centos 6 and is considered experimental. This will install the
        ius repo on the box if disable repo is false. This must be used in conjunction
        with -x <pythonversion>.  For example:
            sh bootstrap.sh -P -y -x python2.7 git v2016.11.3
        The above will install python27 and install the git version of salt using the
        python2.7 executable. This only works for git and pip installations.

EOT
}   # ----------  end of function __usage  ----------


while getopts ':hvnDc:g:Gyx:wk:s:MSNXCPFUKIA:i:Lp:dH:ZbflV:J:j:rR:aq' opt
do
  case "${opt}" in

    h )  __usage; exit 0                                ;;
    v )  echo "$0 -- Version $__ScriptVersion"; exit 0  ;;
    n )  _COLORS=0; __detect_color_support              ;;
    D )  _ECHO_DEBUG=$BS_TRUE                           ;;
    c )  _TEMP_CONFIG_DIR="$OPTARG"                     ;;
    g )  _SALT_REPO_URL=$OPTARG                         ;;

    G )  echowarn "The '-G' option is DEPRECATED and will be removed in the future stable release!"
         echowarn "Bootstrap will always use 'https' protocol to clone from SaltStack GitHub repo."
         echowarn "No need to provide this option anymore, now it is a default behavior."
         ;;

    w )  _DOWNSTREAM_PKG_REPO=$BS_TRUE                  ;;
    k )  _TEMP_KEYS_DIR="$OPTARG"                       ;;
    s )  _SLEEP=$OPTARG                                 ;;
    M )  _INSTALL_MASTER=$BS_TRUE                       ;;
    S )  _INSTALL_SYNDIC=$BS_TRUE                       ;;
    N )  _INSTALL_MINION=$BS_FALSE                      ;;
    X )  _START_DAEMONS=$BS_FALSE                       ;;
    C )  _CONFIG_ONLY=$BS_TRUE                          ;;
    P )  _PIP_ALLOWED=$BS_TRUE                          ;;
    F )  _FORCE_OVERWRITE=$BS_TRUE                      ;;
    U )  _UPGRADE_SYS=$BS_TRUE                          ;;
    K )  _KEEP_TEMP_FILES=$BS_TRUE                      ;;
    I )  _INSECURE_DL=$BS_TRUE                          ;;
    A )  _SALT_MASTER_ADDRESS=$OPTARG                   ;;
    i )  _SALT_MINION_ID=$OPTARG                        ;;
    L )  _INSTALL_CLOUD=$BS_TRUE                        ;;
    p )  _EXTRA_PACKAGES="$_EXTRA_PACKAGES $OPTARG"     ;;
    d )  _DISABLE_SALT_CHECKS=$BS_TRUE                  ;;
    H )  _HTTP_PROXY="$OPTARG"                          ;;
    Z )  _ENABLE_EXTERNAL_ZMQ_REPOS=$BS_TRUE            ;;
    b )  _NO_DEPS=$BS_TRUE                              ;;
    f )  _FORCE_SHALLOW_CLONE=$BS_TRUE                  ;;
    l )  _DISABLE_SSL=$BS_TRUE                          ;;
    V )  _VIRTUALENV_DIR="$OPTARG"                      ;;
    a )  _PIP_ALL=$BS_TRUE                              ;;
    r )  _DISABLE_REPOS=$BS_TRUE                        ;;
    R )  _CUSTOM_REPO_URL=$OPTARG                       ;;
    J )  _CUSTOM_MASTER_CONFIG=$OPTARG                  ;;
    j )  _CUSTOM_MINION_CONFIG=$OPTARG                  ;;
    q )  _QUIET_GIT_INSTALLATION=$BS_TRUE               ;;
    x )  _PY_EXE="$OPTARG"                              ;;
    y )  _INSTALL_PY="$BS_TRUE"                         ;;

    \?)  echo
         echoerror "Option does not exist : $OPTARG"
         __usage
         exit 1
         ;;

  esac    # --- end of case ---
done
shift $((OPTIND-1))


# Define our logging file and pipe paths
LOGFILE="/tmp/$( echo "$__ScriptName" | sed s/.sh/.log/g )"
LOGPIPE="/tmp/$( echo "$__ScriptName" | sed s/.sh/.logpipe/g )"

# Create our logging pipe
# On FreeBSD we have to use mkfifo instead of mknod
mknod "$LOGPIPE" p >/dev/null 2>&1 || mkfifo "$LOGPIPE" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echoerror "Failed to create the named pipe required to log"
    exit 1
fi

# What ever is written to the logpipe gets written to the logfile
tee < "$LOGPIPE" "$LOGFILE" &

# Close STDOUT, reopen it directing it to the logpipe
exec 1>&-
exec 1>"$LOGPIPE"
# Close STDERR, reopen it directing it to the logpipe
exec 2>&-
exec 2>"$LOGPIPE"


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __exit_cleanup
#   DESCRIPTION:  Cleanup any leftovers after script has ended
#
#
#   http://www.unix.com/man-page/POSIX/1posix/trap/
#
#               Signal Number   Signal Name
#               1               SIGHUP
#               2               SIGINT
#               3               SIGQUIT
#               6               SIGABRT
#               9               SIGKILL
#              14               SIGALRM
#              15               SIGTERM
#----------------------------------------------------------------------------------------------------------------------
__exit_cleanup() {
    EXIT_CODE=$?

    if [ "$ITYPE" = "git" ] && [ -d "${_SALT_GIT_CHECKOUT_DIR}" ]; then
        if [ $_KEEP_TEMP_FILES -eq $BS_FALSE ]; then
            # Clean up the checked out repository
            echodebug "Cleaning up the Salt Temporary Git Repository"
            # shellcheck disable=SC2164
            cd "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
            rm -rf "${_SALT_GIT_CHECKOUT_DIR}"
        else
            echowarn "Not cleaning up the Salt Temporary git repository on request"
            echowarn "Note that if you intend to re-run this script using the git approach, you might encounter some issues"
        fi
    fi

    # Remove the logging pipe when the script exits
    if [ -p "$LOGPIPE" ]; then
        echodebug "Removing the logging pipe $LOGPIPE"
        rm -f "$LOGPIPE"
    fi

    # Kill tee when exiting, CentOS, at least requires this
    # shellcheck disable=SC2009
    TEE_PID=$(ps ax | grep tee | grep "$LOGFILE" | awk '{print $1}')

    [ "$TEE_PID" = "" ] && exit $EXIT_CODE

    echodebug "Killing logging pipe tee's with pid(s): $TEE_PID"

    # We need to trap errors since killing tee will cause a 127 errno
    # We also do this as late as possible so we don't "mis-catch" other errors
    __trap_errors() {
        echoinfo "Errors Trapped: $EXIT_CODE"
        # Exit with the "original" exit code, not the trapped code
        exit $EXIT_CODE
    }
    trap "__trap_errors" INT ABRT QUIT TERM

    # Now we're "good" to kill tee
    kill -s TERM "$TEE_PID"

    # In case the 127 errno is not triggered, exit with the "original" exit code
    exit $EXIT_CODE
}
trap "__exit_cleanup" EXIT INT


# Let's discover how we're being called
# shellcheck disable=SC2009
CALLER=$(ps -a -o pid,args | grep $$ | grep -v grep | tr -s ' ' | cut -d ' ' -f 3)

if [ "${CALLER}x" = "${0}x" ]; then
    CALLER="shell pipe"
fi

echoinfo "Running version: ${__ScriptVersion}"
echoinfo "Executed by: ${CALLER}"
echoinfo "Command line: '${__ScriptFullName} ${__ScriptArgs}'"
#echowarn "Running the unstable version of ${__ScriptName}"

# Define installation type
if [ "$#" -gt 0 ];then
    __check_unparsed_options "$*"
    ITYPE=$1
    shift
fi

# Check installation type
if [ "$(echo "$ITYPE" | egrep '(stable|testing|daily|git)')" = "" ]; then
    echoerror "Installation type \"$ITYPE\" is not known..."
    exit 1
fi

# If doing a git install, check what branch/tag/sha will be checked out
if [ "$ITYPE" = "git" ]; then
    if [ "$#" -eq 0 ];then
        GIT_REV="develop"
    else
        GIT_REV="$1"
        shift
    fi

    # Disable shell warning about unbound variable during git install
    STABLE_REV="latest"

# If doing stable install, check if version specified
elif [ "$ITYPE" = "stable" ]; then
    if [ "$#" -eq 0 ];then
        STABLE_REV="latest"
    else
        if [ "$(echo "$1" | egrep '^(latest|1\.6|1\.7|2014\.1|2014\.7|2015\.5|2015\.8|2016\.3|2016\.11|2017\.7)$')" != "" ]; then
            STABLE_REV="$1"
            shift
        elif [ "$(echo "$1" | egrep '^([0-9]*\.[0-9]*\.[0-9]*)$')" != "" ]; then
            STABLE_REV="archive/$1"
            shift
        else
            echo "Unknown stable version: $1 (valid: 1.6, 1.7, 2014.1, 2014.7, 2015.5, 2015.8, 2016.3, 2016.11, 2017.7, latest, \$MAJOR.\$MINOR.\$PATCH)"
            exit 1
        fi
    fi
fi

# Check for any unparsed arguments. Should be an error.
if [ "$#" -gt 0 ]; then
    __usage
    echo
    echoerror "Too many arguments."
    exit 1
fi

# whoami alternative for SunOS
if [ -f /usr/xpg4/bin/id ]; then
    whoami='/usr/xpg4/bin/id -un'
else
    whoami='whoami'
fi

# Root permissions are required to run this script
if [ "$($whoami)" != "root" ]; then
    echoerror "Salt requires root privileges to install. Please re-run this script as root."
    exit 1
fi

# Check that we're actually installing one of minion/master/syndic
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echowarn "Nothing to install or configure"
    exit 1
fi

# Check that we're installing a minion if we're being passed a master address
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_SALT_MASTER_ADDRESS" != "null" ]; then
    echoerror "Don't pass a master address (-A) if no minion is going to be bootstrapped."
    exit 1
fi

# Check that we're installing a minion if we're being passed a minion id
if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_SALT_MINION_ID" != "null" ]; then
    echoerror "Don't pass a minion id (-i) if no minion is going to be bootstrapped."
    exit 1
fi

# Check that we're installing or configuring a master if we're being passed a master config json dict
if [ "$_CUSTOM_MASTER_CONFIG" != "null" ]; then
    if [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoerror "Don't pass a master config JSON dict (-J) if no master is going to be bootstrapped or configured."
        exit 1
    fi
fi

# Check that we're installing or configuring a minion if we're being passed a minion config json dict
if [ "$_CUSTOM_MINION_CONFIG" != "null" ]; then
    if [ "$_INSTALL_MINION" -eq $BS_FALSE ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoerror "Don't pass a minion config JSON dict (-j) if no minion is going to be bootstrapped or configured."
        exit 1
    fi
fi

# If the configuration directory or archive does not exist, error out
if [ "$_TEMP_CONFIG_DIR" != "null" ]; then
    _TEMP_CONFIG_DIR="$(__check_config_dir "$_TEMP_CONFIG_DIR")"
    [ "$_TEMP_CONFIG_DIR" = "null" ] && exit 1
fi

# If the pre-seed keys directory does not exist, error out
if [ "$_TEMP_KEYS_DIR" != "null" ] && [ ! -d "$_TEMP_KEYS_DIR" ]; then
    echoerror "The pre-seed keys directory ${_TEMP_KEYS_DIR} does not exist."
    exit 1
fi

# -a and -V only work from git
if [ "$ITYPE" != "git" ]; then
    if [ $_PIP_ALL -eq $BS_TRUE ]; then
        echoerror "Pip installing all python packages with -a is only possible when installing Salt via git"
        exit 1
    fi
    if [ "$_VIRTUALENV_DIR" != "null" ]; then
        echoerror "Virtualenv installs via -V is only possible when installing Salt via git"
        exit 1
    fi
fi

# Set the _REPO_URL value based on if -R was passed or not. Defaults to repo.saltstack.com.
if [ "$_CUSTOM_REPO_URL" != "null" ]; then
    _REPO_URL="$_CUSTOM_REPO_URL"

    # Check for -r since -R is being passed. Set -r with a warning.
    if [ "$_DISABLE_REPOS" -eq $BS_FALSE ]; then
        echowarn "Detected -R option. No other repositories will be configured when -R is used. Setting -r option to True."
        _DISABLE_REPOS=$BS_TRUE
    fi
fi

# Check the _DISABLE_SSL value and set HTTP or HTTPS.
if [ "$_DISABLE_SSL" -eq $BS_TRUE ]; then
    HTTP_VAL="http"
else
    HTTP_VAL="https"
fi

# Check the _QUIET_GIT_INSTALLATION value and set SETUP_PY_INSTALL_ARGS.
if [ "$_QUIET_GIT_INSTALLATION" -eq $BS_TRUE ]; then
    SETUP_PY_INSTALL_ARGS="-q"
else
    SETUP_PY_INSTALL_ARGS=""
fi

# Handle the insecure flags
if [ "$_INSECURE_DL" -eq $BS_TRUE ]; then
    _CURL_ARGS="${_CURL_ARGS} --insecure"
    _FETCH_ARGS="${_FETCH_ARGS} --no-verify-peer"
    _GPG_ARGS="${_GPG_ARGS} --keyserver-options no-check-cert"
    _WGET_ARGS="${_WGET_ARGS} --no-check-certificate"
else
    _GPG_ARGS="${_GPG_ARGS} --keyserver-options ca-cert-file=/etc/ssl/certs/ca-certificates.crt"
fi

# Export the http_proxy configuration to our current environment
if [ "${_HTTP_PROXY}" != "" ]; then
    export http_proxy="${_HTTP_PROXY}"
    export https_proxy="${_HTTP_PROXY}"
    # Using "deprecated" option here, but that appears the only way to make it work.
    # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=818802
    # and https://bugs.launchpad.net/ubuntu/+source/gnupg2/+bug/1625848
    _GPG_ARGS="${_GPG_ARGS},http-proxy=${_HTTP_PROXY}"
fi

# Work around for 'Docker + salt-bootstrap failure' https://github.com/saltstack/salt-bootstrap/issues/394
if [ "${_DISABLE_SALT_CHECKS}" -eq $BS_FALSE ] && [ -f /tmp/disable_salt_checks ]; then
    # shellcheck disable=SC2016
    echowarn 'Found file: /tmp/disable_salt_checks, setting _DISABLE_SALT_CHECKS=$BS_TRUE'
    _DISABLE_SALT_CHECKS=$BS_TRUE
fi

# Because -a can only be installed into virtualenv
if [ "${_PIP_ALL}" -eq $BS_TRUE ] && [ "${_VIRTUALENV_DIR}" = "null" ]; then
    usage
    # Could possibly set up a default virtualenv location when -a flag is passed
    echoerror "Using -a requires -V because pip pkgs should be siloed from python system pkgs"
    exit 1
fi

# Make sure virtualenv directory does not already exist
if [ -d "${_VIRTUALENV_DIR}" ]; then
    echoerror "The directory ${_VIRTUALENV_DIR} for virtualenv already exists"
    exit 1
fi


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __fetch_url
#  DESCRIPTION:  Retrieves a URL and writes it to a given path
#----------------------------------------------------------------------------------------------------------------------
__fetch_url() {
    # shellcheck disable=SC2086
    curl $_CURL_ARGS -L -s -o "$1" "$2" >/dev/null 2>&1        ||
        wget $_WGET_ARGS -q -O "$1" "$2" >/dev/null 2>&1       ||
            fetch $_FETCH_ARGS -q -o "$1" "$2" >/dev/null 2>&1 ||  # FreeBSD
                fetch -q -o "$1" "$2" >/dev/null 2>&1          ||  # Pre FreeBSD 10
                    ftp -o "$1" "$2" >/dev/null 2>&1               # OpenBSD
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#         NAME:  __fetch_verify
#  DESCRIPTION:  Retrieves a URL, verifies its content and writes it to standard output
#----------------------------------------------------------------------------------------------------------------------
__fetch_verify() {
    fetch_verify_url="$1"
    fetch_verify_sum="$2"
    fetch_verify_size="$3"

    fetch_verify_tmpf=$(mktemp) && \
    __fetch_url "$fetch_verify_tmpf" "$fetch_verify_url" && \
    test "$(stat --format=%s "$fetch_verify_tmpf")" -eq "$fetch_verify_size" && \
    test "$(md5sum "$fetch_verify_tmpf" | awk '{ print $1 }')" = "$fetch_verify_sum" && \
    cat "$fetch_verify_tmpf" && \
    rm -f "$fetch_verify_tmpf"
    if [ $? -eq 0 ]; then
        return 0
    fi
    echo "Failed verification of $fetch_verify_url"
    return 1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_hardware_info
#   DESCRIPTION:  Discover hardware information
#----------------------------------------------------------------------------------------------------------------------
__gather_hardware_info() {
    if [ -f /proc/cpuinfo ]; then
        CPU_VENDOR_ID=$(awk '/vendor_id|Processor/ {sub(/-.*$/,"",$3); print $3; exit}' /proc/cpuinfo )
    elif [ -f /usr/bin/kstat ]; then
        # SmartOS.
        # Solaris!?
        # This has only been tested for a GenuineIntel CPU
        CPU_VENDOR_ID=$(/usr/bin/kstat -p cpu_info:0:cpu_info0:vendor_id | awk '{print $2}')
    else
        CPU_VENDOR_ID=$( sysctl -n hw.model )
    fi
    # shellcheck disable=SC2034
    CPU_VENDOR_ID_L=$( echo "$CPU_VENDOR_ID" | tr '[:upper:]' '[:lower:]' )
    CPU_ARCH=$(uname -m 2>/dev/null || uname -p 2>/dev/null || echo "unknown")
    CPU_ARCH_L=$( echo "$CPU_ARCH" | tr '[:upper:]' '[:lower:]' )
}
__gather_hardware_info


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_os_info
#   DESCRIPTION:  Discover operating system information
#----------------------------------------------------------------------------------------------------------------------
__gather_os_info() {
    OS_NAME=$(uname -s 2>/dev/null)
    OS_NAME_L=$( echo "$OS_NAME" | tr '[:upper:]' '[:lower:]' )
    OS_VERSION=$(uname -r)
    # shellcheck disable=SC2034
    OS_VERSION_L=$( echo "$OS_VERSION" | tr '[:upper:]' '[:lower:]' )
}
__gather_os_info


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __parse_version_string
#   DESCRIPTION:  Parse version strings ignoring the revision.
#                 MAJOR.MINOR.REVISION becomes MAJOR.MINOR
#----------------------------------------------------------------------------------------------------------------------
__parse_version_string() {
    VERSION_STRING="$1"
    PARSED_VERSION=$(
        echo "$VERSION_STRING" |
        sed -e 's/^/#/' \
            -e 's/^#[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\)\(\.[0-9][0-9]*\).*$/\1/' \
            -e 's/^#[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\).*$/\1/' \
            -e 's/^#[^0-9]*\([0-9][0-9]*\).*$/\1/' \
            -e 's/^#.*$//'
    )
    echo "$PARSED_VERSION"
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __derive_debian_numeric_version
#   DESCRIPTION:  Derive the numeric version from a Debian version string.
#----------------------------------------------------------------------------------------------------------------------
__derive_debian_numeric_version() {
    NUMERIC_VERSION=""
    INPUT_VERSION="$1"
    if echo "$INPUT_VERSION" | grep -q '^[0-9]'; then
        NUMERIC_VERSION="$INPUT_VERSION"
    elif [ -z "$INPUT_VERSION" ] && [ -f "/etc/debian_version" ]; then
        INPUT_VERSION="$(cat /etc/debian_version)"
    fi
    if [ -z "$NUMERIC_VERSION" ]; then
        if [ "$INPUT_VERSION" = "wheezy/sid" ]; then
            # I've found an EC2 wheezy image which did not tell its version
            NUMERIC_VERSION=$(__parse_version_string "7.0")
        elif [ "$INPUT_VERSION" = "jessie/sid" ]; then
            NUMERIC_VERSION=$(__parse_version_string "8.0")
        elif [ "$INPUT_VERSION" = "stretch/sid" ]; then
            NUMERIC_VERSION=$(__parse_version_string "9.0")
        elif [ "$INPUT_VERSION" = "buster/sid" ]; then
            # Let's start detecting the upcoming Debian 10 (Buster) release
            NUMERIC_VERSION=$(__parse_version_string "10.0")
        else
            echowarn "Unable to parse the Debian Version (codename: '$INPUT_VERSION')"
        fi
    fi
    echo "$NUMERIC_VERSION"
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __unquote_string
#   DESCRIPTION:  Strip single or double quotes from the provided string.
#----------------------------------------------------------------------------------------------------------------------
__unquote_string() {
    echo "$*" | sed -e "s/^\([\"\']\)\(.*\)\1\$/\2/g"
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __camelcase_split
#   DESCRIPTION:  Convert 'CamelCased' strings to 'Camel Cased'
#----------------------------------------------------------------------------------------------------------------------
__camelcase_split() {
    echo "$*" | sed -e 's/\([^[:upper:][:punct:]]\)\([[:upper:]]\)/\1 \2/g'
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __strip_duplicates
#   DESCRIPTION:  Strip duplicate strings
#----------------------------------------------------------------------------------------------------------------------
__strip_duplicates() {
    echo "$*" | tr -s '[:space:]' '\n' | awk '!x[$0]++'
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __sort_release_files
#   DESCRIPTION:  Custom sort function. Alphabetical or numerical sort is not
#                 enough.
#----------------------------------------------------------------------------------------------------------------------
__sort_release_files() {
    KNOWN_RELEASE_FILES=$(echo "(arch|alpine|centos|debian|ubuntu|fedora|redhat|suse|\
        mandrake|mandriva|gentoo|slackware|turbolinux|unitedlinux|void|lsb|system|\
        oracle|os)(-|_)(release|version)" | sed -r 's:[[:space:]]::g')
    primary_release_files=""
    secondary_release_files=""
    # Sort know VS un-known files first
    for release_file in $(echo "${@}" | sed -r 's:[[:space:]]:\n:g' | sort -f | uniq); do
        match=$(echo "$release_file" | egrep -i "${KNOWN_RELEASE_FILES}")
        if [ "${match}" != "" ]; then
            primary_release_files="${primary_release_files} ${release_file}"
        else
            secondary_release_files="${secondary_release_files} ${release_file}"
        fi
    done

    # Now let's sort by know files importance, max important goes last in the max_prio list
    max_prio="redhat-release centos-release oracle-release fedora-release"
    for entry in $max_prio; do
        if [ "$(echo "${primary_release_files}" | grep "$entry")" != "" ]; then
            primary_release_files=$(echo "${primary_release_files}" | sed -e "s:\(.*\)\($entry\)\(.*\):\2 \1 \3:g")
        fi
    done
    # Now, least important goes last in the min_prio list
    min_prio="lsb-release"
    for entry in $min_prio; do
        if [ "$(echo "${primary_release_files}" | grep "$entry")" != "" ]; then
            primary_release_files=$(echo "${primary_release_files}" | sed -e "s:\(.*\)\($entry\)\(.*\):\1 \3 \2:g")
        fi
    done

    # Echo the results collapsing multiple white-space into a single white-space
    echo "${primary_release_files} ${secondary_release_files}" | sed -r 's:[[:space:]]+:\n:g'
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_linux_system_info
#   DESCRIPTION:  Discover Linux system information
#----------------------------------------------------------------------------------------------------------------------
__gather_linux_system_info() {
    DISTRO_NAME=""
    DISTRO_VERSION=""

    # Let's test if the lsb_release binary is available
    rv=$(lsb_release >/dev/null 2>&1)
    if [ $? -eq 0 ]; then
        DISTRO_NAME=$(lsb_release -si)
        if [ "${DISTRO_NAME}" = "Scientific" ]; then
            DISTRO_NAME="Scientific Linux"
        elif [ "$(echo "$DISTRO_NAME" | grep ^CloudLinux)" != "" ]; then
            DISTRO_NAME="Cloud Linux"
        elif [ "$(echo "$DISTRO_NAME" | grep ^RedHat)" != "" ]; then
            # Let's convert 'CamelCased' to 'Camel Cased'
            n=$(__camelcase_split "$DISTRO_NAME")
            # Skip setting DISTRO_NAME this time, splitting CamelCase has failed.
            # See https://github.com/saltstack/salt-bootstrap/issues/918
            [ "$n" = "$DISTRO_NAME" ] && DISTRO_NAME="" || DISTRO_NAME="$n"
        elif [ "${DISTRO_NAME}" = "openSUSE project" ]; then
            # lsb_release -si returns "openSUSE project" on openSUSE 12.3
            DISTRO_NAME="opensuse"
        elif [ "${DISTRO_NAME}" = "SUSE LINUX" ]; then
            if [ "$(lsb_release -sd | grep -i opensuse)" != "" ]; then
                # openSUSE 12.2 reports SUSE LINUX on lsb_release -si
                DISTRO_NAME="opensuse"
            else
                # lsb_release -si returns "SUSE LINUX" on SLES 11 SP3
                DISTRO_NAME="suse"
            fi
        elif [ "${DISTRO_NAME}" = "EnterpriseEnterpriseServer" ]; then
            # This the Oracle Linux Enterprise ID before ORACLE LINUX 5 UPDATE 3
            DISTRO_NAME="Oracle Linux"
        elif [ "${DISTRO_NAME}" = "OracleServer" ]; then
            # This the Oracle Linux Server 6.5
            DISTRO_NAME="Oracle Linux"
        elif [ "${DISTRO_NAME}" = "AmazonAMI" ]; then
            DISTRO_NAME="Amazon Linux AMI"
        elif [ "${DISTRO_NAME}" = "ManjaroLinux" ]; then
            DISTRO_NAME="Arch Linux"
        elif [ "${DISTRO_NAME}" = "Arch" ]; then
            DISTRO_NAME="Arch Linux"
            return
        fi
        rv=$(lsb_release -sr)
        [ "${rv}" != "" ] && DISTRO_VERSION=$(__parse_version_string "$rv")
    elif [ -f /etc/lsb-release ]; then
        # We don't have the lsb_release binary, though, we do have the file it parses
        DISTRO_NAME=$(grep DISTRIB_ID /etc/lsb-release | sed -e 's/.*=//')
        rv=$(grep DISTRIB_RELEASE /etc/lsb-release | sed -e 's/.*=//')
        [ "${rv}" != "" ] && DISTRO_VERSION=$(__parse_version_string "$rv")
    fi

    if [ "$DISTRO_NAME" != "" ] && [ "$DISTRO_VERSION" != "" ]; then
        # We already have the distribution name and version
        return
    fi
    # shellcheck disable=SC2035,SC2086
    for rsource in $(__sort_release_files "$(
            cd /etc && /bin/ls *[_-]release *[_-]version 2>/dev/null | env -i sort | \
            sed -e '/^redhat-release$/d' -e '/^lsb-release$/d'; \
            echo redhat-release lsb-release
            )"); do

        [ ! -f "/etc/${rsource}" ] && continue      # Does not exist

        n=$(echo "${rsource}" | sed -e 's/[_-]release$//' -e 's/[_-]version$//')
        shortname=$(echo "${n}" | tr '[:upper:]' '[:lower:]')
        if [ "$shortname" = "debian" ]; then
            rv=$(__derive_debian_numeric_version "$(cat /etc/${rsource})")
        else
            rv=$( (grep VERSION "/etc/${rsource}"; cat "/etc/${rsource}") | grep '[0-9]' | sed -e 'q' )
        fi
        [ "${rv}" = "" ] && [ "$shortname" != "arch" ] && continue  # There's no version information. Continue to next rsource
        v=$(__parse_version_string "$rv")
        case $shortname in
            redhat             )
                if [ "$(egrep 'CentOS' /etc/${rsource})" != "" ]; then
                    n="CentOS"
                elif [ "$(egrep 'Scientific' /etc/${rsource})" != "" ]; then
                    n="Scientific Linux"
                elif [ "$(egrep 'Red Hat Enterprise Linux' /etc/${rsource})" != "" ]; then
                    n="<R>ed <H>at <E>nterprise <L>inux"
                else
                    n="<R>ed <H>at <L>inux"
                fi
                ;;
            arch               ) n="Arch Linux"     ;;
            alpine             ) n="Alpine Linux"   ;;
            centos             ) n="CentOS"         ;;
            debian             ) n="Debian"         ;;
            ubuntu             ) n="Ubuntu"         ;;
            fedora             ) n="Fedora"         ;;
            suse               ) n="SUSE"           ;;
            mandrake*|mandriva ) n="Mandriva"       ;;
            gentoo             ) n="Gentoo"         ;;
            slackware          ) n="Slackware"      ;;
            turbolinux         ) n="TurboLinux"     ;;
            unitedlinux        ) n="UnitedLinux"    ;;
            void               ) n="VoidLinux"      ;;
            oracle             ) n="Oracle Linux"   ;;
            system             )
                while read -r line; do
                    [ "${n}x" != "systemx" ] && break
                    case "$line" in
                        *Amazon*Linux*AMI*)
                            n="Amazon Linux AMI"
                            break
                    esac
                done < "/etc/${rsource}"
                ;;
            os                 )
                nn="$(__unquote_string "$(grep '^ID=' /etc/os-release | sed -e 's/^ID=\(.*\)$/\1/g')")"
                rv="$(__unquote_string "$(grep '^VERSION_ID=' /etc/os-release | sed -e 's/^VERSION_ID=\(.*\)$/\1/g')")"
                [ "${rv}" != "" ] && v=$(__parse_version_string "$rv") || v=""
                case $(echo "${nn}" | tr '[:upper:]' '[:lower:]') in
                    alpine      )
                        n="Alpine Linux"
                        v="${rv}"
                        ;;
                    amzn        )
                        # Amazon AMI's after 2014.09 match here
                        n="Amazon Linux AMI"
                        ;;
                    arch        )
                        n="Arch Linux"
                        v=""  # Arch Linux does not provide a version.
                        ;;
                    cloudlinux  )
                        n="Cloud Linux"
                        ;;
                    debian      )
                        n="Debian"
                        v=$(__derive_debian_numeric_version "$v")
                        ;;
                    sles        )
                        n="SUSE"
                        v="${rv}"
                        ;;
                    *           )
                        n=${nn}
                        ;;
                esac
                ;;
            *                  ) n="${n}"           ;
        esac
        DISTRO_NAME=$n
        DISTRO_VERSION=$v
        break
    done
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __install_python()
#   DESCRIPTION:  Install a different version of python on a host. Currently this has only been tested on CentOS 6 and
#                 is considered experimental.
#----------------------------------------------------------------------------------------------------------------------
__install_python() {
    if [ "$_PY_EXE" = "" ]; then
        echoerror "Must specify -x <pythonversion> with -y to install a specific python version"
        exit 1
    fi

    PY_PKG_V=$(echo "$_PY_EXE" | sed -r "s/\.//g")
    __PACKAGES="${PY_PKG_V}"


    if [ ${_DISABLE_REPOS} -eq ${BS_FALSE} ]; then
        echoinfo "Attempting to install a repo to help provide a separate python package"
        echoinfo "$DISTRO_NAME_L"
        case "$DISTRO_NAME_L" in
            "red_hat"|"centos")
                __PYTHON_REPO_URL="https://centos${DISTRO_MAJOR_VERSION}.iuscommunity.org/ius-release.rpm"
                ;;
            *)
                echoerror "Installing a repo to provide a python package is only supported on Redhat/CentOS.
                If a repo is already available, please try running script with -r."
                exit 1
                ;;
        esac

        echoinfo "Installing IUS repo"
        __yum_install_noinput "${__PYTHON_REPO_URL}" || return 1
    fi

    echoinfo "Installing ${__PACKAGES}"
    __yum_install_noinput "${__PACKAGES}" || return 1
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_sunos_system_info
#   DESCRIPTION:  Discover SunOS system info
#----------------------------------------------------------------------------------------------------------------------
__gather_sunos_system_info() {
    if [ -f /sbin/uname ]; then
        DISTRO_VERSION=$(/sbin/uname -X | awk '/[kK][eE][rR][nN][eE][lL][iI][dD]/ { print $3 }')
    fi

    DISTRO_NAME=""
    if [ -f /etc/release ]; then
        while read -r line; do
            [ "${DISTRO_NAME}" != "" ] && break
            case "$line" in
                *OpenIndiana*oi_[0-9]*)
                    DISTRO_NAME="OpenIndiana"
                    DISTRO_VERSION=$(echo "$line" | sed -nr "s/OpenIndiana(.*)oi_([[:digit:]]+)(.*)/\2/p")
                    break
                    ;;
                *OpenSolaris*snv_[0-9]*)
                    DISTRO_NAME="OpenSolaris"
                    DISTRO_VERSION=$(echo "$line" | sed -nr "s/OpenSolaris(.*)snv_([[:digit:]]+)(.*)/\2/p")
                    break
                    ;;
                *Oracle*Solaris*[0-9]*)
                    DISTRO_NAME="Oracle Solaris"
                    DISTRO_VERSION=$(echo "$line" | sed -nr "s/(Oracle Solaris) ([[:digit:]]+)(.*)/\2/p")
                    break
                    ;;
                *Solaris*)
                    DISTRO_NAME="Solaris"
                    # Let's make sure we not actually on a Joyent's SmartOS VM since some releases
                    # don't have SmartOS in `/etc/release`, only `Solaris`
                    uname -v | grep joyent >/dev/null 2>&1
                    if [ $? -eq 0 ]; then
                        DISTRO_NAME="SmartOS"
                    fi
                    break
                    ;;
                *NexentaCore*)
                    DISTRO_NAME="Nexenta Core"
                    break
                    ;;
                *SmartOS*)
                    DISTRO_NAME="SmartOS"
                    break
                    ;;
                *OmniOS*)
                    DISTRO_NAME="OmniOS"
                    DISTRO_VERSION=$(echo "$line" | awk '{print $3}')
                    _SIMPLIFY_VERSION=$BS_FALSE
                    break
                    ;;
            esac
        done < /etc/release
    fi

    if [ "${DISTRO_NAME}" = "" ]; then
        DISTRO_NAME="Solaris"
        DISTRO_VERSION=$(
            echo "${OS_VERSION}" |
            sed -e 's;^4\.;1.;' \
                -e 's;^5\.\([0-6]\)[^0-9]*$;2.\1;' \
                -e 's;^5\.\([0-9][0-9]*\).*;\1;'
        )
    fi

    if [ "${DISTRO_NAME}" = "SmartOS" ]; then
        VIRTUAL_TYPE="smartmachine"
        if [ "$(zonename)" = "global" ]; then
            VIRTUAL_TYPE="global"
        fi
    fi
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_bsd_system_info
#   DESCRIPTION:  Discover OpenBSD, NetBSD and FreeBSD systems information
#----------------------------------------------------------------------------------------------------------------------
__gather_bsd_system_info() {
    DISTRO_NAME=${OS_NAME}
    DISTRO_VERSION=$(echo "${OS_VERSION}" | sed -e 's;[()];;' -e 's/-.*$//')
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __gather_system_info
#   DESCRIPTION:  Discover which system and distribution we are running.
#----------------------------------------------------------------------------------------------------------------------
__gather_system_info() {
    case ${OS_NAME_L} in
        linux )
            __gather_linux_system_info
            ;;
        sunos )
            __gather_sunos_system_info
            ;;
        openbsd|freebsd|netbsd )
            __gather_bsd_system_info
            ;;
        * )
            echoerror "${OS_NAME} not supported.";
            exit 1
            ;;
    esac

}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __ubuntu_derivatives_translation
#   DESCRIPTION:  Map Ubuntu derivatives to their Ubuntu base versions.
#                 If distro has a known Ubuntu base version, use those install
#                 functions by pretending to be Ubuntu (i.e. change global vars)
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__ubuntu_derivatives_translation() {
    UBUNTU_DERIVATIVES="(trisquel|linuxmint|linaro|elementary_os|neon)"
    # Mappings
    trisquel_6_ubuntu_base="12.04"
    linuxmint_13_ubuntu_base="12.04"
    linuxmint_17_ubuntu_base="14.04"
    linuxmint_18_ubuntu_base="16.04"
    linaro_12_ubuntu_base="12.04"
    elementary_os_02_ubuntu_base="12.04"
    neon_16_ubuntu_base="16.04"

    # Translate Ubuntu derivatives to their base Ubuntu version
    match=$(echo "$DISTRO_NAME_L" | egrep ${UBUNTU_DERIVATIVES})

    if [ "${match}" != "" ]; then
        case $match in
            "elementary_os")
                _major=$(echo "$DISTRO_VERSION" | sed 's/\.//g')
                ;;
            "linuxmint")
                export LSB_ETC_LSB_RELEASE=/etc/upstream-release/lsb-release
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                ;;
            *)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                ;;
        esac

        _ubuntu_version=$(eval echo "\$${match}_${_major}_ubuntu_base")

        if [ "$_ubuntu_version" != "" ]; then
            echodebug "Detected Ubuntu $_ubuntu_version derivative"
            DISTRO_NAME_L="ubuntu"
            DISTRO_VERSION="$_ubuntu_version"
        fi
    fi
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_dpkg_architecture
#   DESCRIPTION:  Determine the primary architecture for packages to install on Debian and derivatives
#                 and issue all necessary error messages.
#----------------------------------------------------------------------------------------------------------------------
__check_dpkg_architecture() {
    if __check_command_exists dpkg; then
        DPKG_ARCHITECTURE="$(dpkg --print-architecture)"
    else
        echoerror "dpkg: command not found."
        return 1
    fi

    __REPO_ARCH="$DPKG_ARCHITECTURE"
    __return_code=0

    case $DPKG_ARCHITECTURE in
        "i386")
            error_msg="$_REPO_URL likely doesn't have all required 32-bit packages for $DISTRO_NAME $DISTRO_MAJOR_VERSION."
            # amd64 is just a part of repository URI, 32-bit pkgs are hosted under the same location
            __REPO_ARCH="amd64"
            ;;
        "amd64")
            error_msg=""
            ;;
        "armhf")
            if [ "$DISTRO_NAME_L" = "ubuntu" ] || [ "$DISTRO_MAJOR_VERSION" -lt 8 ]; then
                error_msg="Support for armhf packages at $_REPO_URL is limited to Debian/Raspbian 8 platforms."
                __return_code=1
            else
                error_msg=""
            fi
            ;;
        *)
            error_msg="$_REPO_URL doesn't have packages for your system architecture: $DPKG_ARCHITECTURE."
            __return_code=1
            ;;
    esac

    if [ "${error_msg}" != "" ]; then
        echoerror "${error_msg}"
        if [ "$ITYPE" != "git" ]; then
            echoerror "You can try git installation mode, i.e.: sh ${__ScriptName} git v2016.11.5."
            echoerror "It may be necessary to use git installation mode with pip and disable the SaltStack apt repository."
            echoerror "For example:"
            echoerror "    sh ${__ScriptName} -r -P git v2016.11.5"
        fi
    fi

    if [ "${__return_code}" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __ubuntu_codename_translation
#   DESCRIPTION:  Map Ubuntu major versions to their corresponding codenames
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__ubuntu_codename_translation() {
    case $DISTRO_MINOR_VERSION in
        "04")
            _april="yes"
            ;;
        "10")
            _april=""
            ;;
        *)
            _april="yes"
            ;;
    esac

    case $DISTRO_MAJOR_VERSION in
        "12")
            DISTRO_CODENAME="precise"
            ;;
        "14")
            DISTRO_CODENAME="trusty"
            ;;
        "16")
            if [ "$_april" ]; then
                DISTRO_CODENAME="xenial"
            else
                DISTRO_CODENAME="yakkety"
            fi
            ;;
        "17")
            if [ "$_april" ]; then
                DISTRO_CODENAME="zesty"
            fi
            ;;
        *)
            DISTRO_CODENAME="trusty"
            ;;
    esac
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __debian_derivatives_translation
#   DESCRIPTION:  Map Debian derivatives to their Debian base versions.
#                 If distro has a known Debian base version, use those install
#                 functions by pretending to be Debian (i.e. change global vars)
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__debian_derivatives_translation() {
    # If the file does not exist, return
    [ ! -f /etc/os-release ] && return

    DEBIAN_DERIVATIVES="(cumulus_.+|devuan|kali|linuxmint|raspbian)"
    # Mappings
    cumulus_2_debian_base="7.0"
    cumulus_3_debian_base="8.0"
    devuan_1_debian_base="8.0"
    devuan_2_debian_base="9.0"
    kali_1_debian_base="7.0"
    linuxmint_1_debian_base="8.0"
    raspbian_8_debian_base="8.0"
    raspbian_9_debian_base="9.0"

    # Translate Debian derivatives to their base Debian version
    match=$(echo "$DISTRO_NAME_L" | egrep ${DEBIAN_DERIVATIVES})

    if [ "${match}" != "" ]; then
        case $match in
            cumulus_*)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="cumulus"
                ;;
            devuan)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="devuan"
                ;;
            kali)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="kali"
                ;;
            linuxmint)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="linuxmint"
                ;;
            raspbian)
                _major=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
                _debian_derivative="raspbian"
                ;;
        esac

        _debian_version=$(eval echo "\$${_debian_derivative}_${_major}_debian_base" 2>/dev/null)

        if [ "$_debian_version" != "" ]; then
            echodebug "Detected Debian $_debian_version derivative"
            DISTRO_NAME_L="debian"
            DISTRO_VERSION="$_debian_version"
            DISTRO_MAJOR_VERSION="$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')"
        fi
    fi
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __debian_codename_translation
#   DESCRIPTION:  Map Debian major versions to their corresponding code names
#----------------------------------------------------------------------------------------------------------------------
# shellcheck disable=SC2034
__debian_codename_translation() {

    case $DISTRO_MAJOR_VERSION in
        "7")
            DISTRO_CODENAME="wheezy"
            ;;
        "8")
            DISTRO_CODENAME="jessie"
            ;;
        "9")
            DISTRO_CODENAME="stretch"
            ;;
        "10")
            DISTRO_CODENAME="buster"
            ;;
        *)
            DISTRO_CODENAME="jessie"
            ;;
    esac
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_end_of_life_versions
#   DESCRIPTION:  Check for end of life distribution versions
#----------------------------------------------------------------------------------------------------------------------
__check_end_of_life_versions() {
    case "${DISTRO_NAME_L}" in
        debian)
            # Debian versions below 7 are not supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 7 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://wiki.debian.org/DebianReleases"
                exit 1
            fi
            ;;

        ubuntu)
            # Ubuntu versions not supported
            #
            #  < 14.04
            #  = 14.10
            #  = 15.04, 15.10
            if [ "$DISTRO_MAJOR_VERSION" -lt 14 ] || \
                [ "$DISTRO_MAJOR_VERSION" -eq 15 ] || \
                ([ "$DISTRO_MAJOR_VERSION" -lt 16 ] && [ "$DISTRO_MINOR_VERSION" -eq 10 ]); then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://wiki.ubuntu.com/Releases"
                exit 1
            fi
            ;;

        opensuse)
            # openSUSE versions not supported
            #
            #  <= 13.X
            #  <= 42.1
            if [ "$DISTRO_MAJOR_VERSION" -le 13 ] || \
                ([ "$DISTRO_MAJOR_VERSION" -eq 42 ] && [ "$DISTRO_MINOR_VERSION" -le 1 ]); then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    http://en.opensuse.org/Lifetime"
                exit 1
            fi
            ;;

        suse)
            # SuSE versions not supported
            #
            # < 11 SP4
            # < 12 SP2
            SUSE_PATCHLEVEL=$(awk '/PATCHLEVEL/ {print $3}' /etc/SuSE-release )
            if [ "${SUSE_PATCHLEVEL}" = "" ]; then
                SUSE_PATCHLEVEL="00"
            fi
            if [ "$DISTRO_MAJOR_VERSION" -lt 11 ] || \
                ([ "$DISTRO_MAJOR_VERSION" -eq 11 ] && [ "$SUSE_PATCHLEVEL" -lt 04 ]) || \
                ([ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$SUSE_PATCHLEVEL" -lt 02 ]); then
                echoerror "Versions lower than SuSE 11 SP4 or 12 SP2 are not supported."
                echoerror "Please consider upgrading to the next stable"
                echoerror "    https://www.suse.com/lifecycle/"
                exit 1
            fi
            ;;

        fedora)
            # Fedora lower than 25 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 25 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://fedoraproject.org/wiki/Releases"
                exit 1
            fi
            ;;

        centos)
            # CentOS versions lower than 6 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    http://wiki.centos.org/Download"
                exit 1
            fi
            ;;

        red_hat*linux)
            # Red Hat (Enterprise) Linux versions lower than 6 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://access.redhat.com/support/policy/updates/errata/"
                exit 1
            fi
            ;;

        oracle*linux)
            # Oracle Linux versions lower than 6 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    http://www.oracle.com/us/support/library/elsp-lifetime-069338.pdf"
                exit 1
            fi
            ;;

        scientific*linux)
            # Scientific Linux versions lower than 6 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://www.scientificlinux.org/downloads/sl-versions/"
                exit 1
            fi
            ;;

        cloud*linux)
            # Cloud Linux versions lower than 6 are no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 6 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://docs.cloudlinux.com/index.html?cloudlinux_life-cycle.html"
                exit 1
            fi
            ;;

        amazon*linux*ami)
            # Amazon Linux versions lower than 2012.0X no longer supported
            if [ "$DISTRO_MAJOR_VERSION" -lt 2012 ]; then
                echoerror "End of life distributions are not supported."
                echoerror "Please consider upgrading to the next stable. See:"
                echoerror "    https://aws.amazon.com/amazon-linux-ami/"
                exit 1
            fi
            ;;

        freebsd)
            # FreeBSD versions lower than 9.1 are not supported.
            if ([ "$DISTRO_MAJOR_VERSION" -eq 9 ] && [ "$DISTRO_MINOR_VERSION" -lt 01 ]) || [ "$DISTRO_MAJOR_VERSION" -lt 9 ]; then
                echoerror "Versions lower than FreeBSD 9.1 are not supported."
                exit 1
            fi
            ;;

        *)
            ;;
    esac
}


__gather_system_info

echo
echoinfo "System Information:"
echoinfo "  CPU:          ${CPU_VENDOR_ID}"
echoinfo "  CPU Arch:     ${CPU_ARCH}"
echoinfo "  OS Name:      ${OS_NAME}"
echoinfo "  OS Version:   ${OS_VERSION}"
echoinfo "  Distribution: ${DISTRO_NAME} ${DISTRO_VERSION}"
echo

# Simplify distro name naming on functions
DISTRO_NAME_L=$(echo "$DISTRO_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-zA-Z0-9_ ]//g' | sed -re 's/([[:space:]])+/_/g')

# Simplify version naming on functions
if [ "$DISTRO_VERSION" = "" ] || [ ${_SIMPLIFY_VERSION} -eq $BS_FALSE ]; then
    DISTRO_MAJOR_VERSION=""
    DISTRO_MINOR_VERSION=""
    PREFIXED_DISTRO_MAJOR_VERSION=""
    PREFIXED_DISTRO_MINOR_VERSION=""
else
    DISTRO_MAJOR_VERSION=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).*/\1/g')
    DISTRO_MINOR_VERSION=$(echo "$DISTRO_VERSION" | sed 's/^\([0-9]*\).\([0-9]*\).*/\2/g')
    PREFIXED_DISTRO_MAJOR_VERSION="_${DISTRO_MAJOR_VERSION}"
    if [ "${PREFIXED_DISTRO_MAJOR_VERSION}" = "_" ]; then
        PREFIXED_DISTRO_MAJOR_VERSION=""
    fi
    PREFIXED_DISTRO_MINOR_VERSION="_${DISTRO_MINOR_VERSION}"
    if [ "${PREFIXED_DISTRO_MINOR_VERSION}" = "_" ]; then
        PREFIXED_DISTRO_MINOR_VERSION=""
    fi
fi

# For Ubuntu derivatives, pretend to be their Ubuntu base version
__ubuntu_derivatives_translation

# For Debian derivates, pretend to be their Debian base version
__debian_derivatives_translation

# Fail soon for end of life versions
__check_end_of_life_versions

echodebug "Binaries will be searched using the following \$PATH: ${PATH}"

# Let users know that we'll use a proxy
if [ "${_HTTP_PROXY}" != "" ]; then
    echoinfo "Using http proxy $_HTTP_PROXY"
fi

# Let users know what's going to be installed/configured
if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
    if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoinfo "Installing minion"
    else
        echoinfo "Configuring minion"
    fi
fi

if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
    if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoinfo "Installing master"
    else
        echoinfo "Configuring master"
    fi
fi

if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
    if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
        echoinfo "Installing syndic"
    else
        echoinfo "Configuring syndic"
    fi
fi

if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echoinfo "Installing salt-cloud and required python-libcloud package"
fi

if [ $_START_DAEMONS -eq $BS_FALSE ]; then
    echoinfo "Daemons will not be started"
fi

if [ "${DISTRO_NAME_L}" = "ubuntu" ]; then
  # For ubuntu versions, obtain the codename from the release version
  __ubuntu_codename_translation
elif [ "${DISTRO_NAME_L}" = "debian" ]; then
  # For debian versions, obtain the codename from the release version
  __debian_codename_translation
fi

# Only Ubuntu has daily packages, let's let users know about that
if ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ "$ITYPE" = "daily" ]); then
    echoerror "${DISTRO_NAME} does not have daily packages support"
    exit 1
elif ([ "$(echo "${DISTRO_NAME_L}" | egrep '(debian|ubuntu|centos|red_hat|oracle|scientific|amazon)')" = "" ] && [ "$ITYPE" = "stable" ] && [ "$STABLE_REV" != "latest" ]); then
    echoerror "${DISTRO_NAME} does not have major version pegged packages support"
    exit 1
fi

# Only RedHat based distros have testing support
if [ "${ITYPE}" = "testing" ]; then
    if [ "$(echo "${DISTRO_NAME_L}" | egrep '(centos|red_hat|amazon|oracle)')" = "" ]; then
        echoerror "${DISTRO_NAME} does not have testing packages support"
        exit 1
    fi
    _EPEL_REPO="epel-testing"
fi

# Only Ubuntu has support for installing to virtualenvs
if ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ "$_VIRTUALENV_DIR" != "null" ]); then
    echoerror "${DISTRO_NAME} does not have -V support"
    exit 1
fi

# Only Ubuntu has support for pip installing all packages
if ([ "${DISTRO_NAME_L}" != "ubuntu" ] && [ $_PIP_ALL -eq $BS_TRUE ]); then
    echoerror "${DISTRO_NAME} does not have -a support"
    exit 1
fi


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __function_defined
#   DESCRIPTION:  Checks if a function is defined within this scripts scope
#    PARAMETERS:  function name
#       RETURNS:  0 or 1 as in defined or not defined
#----------------------------------------------------------------------------------------------------------------------
__function_defined() {
    FUNC_NAME=$1
    if [ "$(command -v "$FUNC_NAME")" != "" ]; then
        echoinfo "Found function $FUNC_NAME"
        return 0
    fi
    echodebug "$FUNC_NAME not found...."
    return 1
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __apt_get_install_noinput
#   DESCRIPTION:  (DRY) apt-get install with noinput options
#    PARAMETERS:  packages
#----------------------------------------------------------------------------------------------------------------------
__apt_get_install_noinput() {
    apt-get install -y -o DPkg::Options::=--force-confold "${@}"; return $?
}   # ----------  end of function __apt_get_install_noinput  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __apt_get_upgrade_noinput
#   DESCRIPTION:  (DRY) apt-get upgrade with noinput options
#----------------------------------------------------------------------------------------------------------------------
__apt_get_upgrade_noinput() {
    apt-get upgrade -y -o DPkg::Options::=--force-confold; return $?
}   # ----------  end of function __apt_get_upgrade_noinput  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __apt_key_fetch
#   DESCRIPTION:  Download and import GPG public key for "apt-secure"
#    PARAMETERS:  url
#----------------------------------------------------------------------------------------------------------------------
__apt_key_fetch() {
    url=$1

    # shellcheck disable=SC2086
    apt-key adv ${_GPG_ARGS} --fetch-keys "$url"; return $?
}   # ----------  end of function __apt_key_fetch  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __rpm_import_gpg
#   DESCRIPTION:  Download and import GPG public key to rpm database
#    PARAMETERS:  url
#----------------------------------------------------------------------------------------------------------------------
__rpm_import_gpg() {
    url=$1

    if __check_command_exists mktemp; then
        tempfile="$(mktemp /tmp/salt-gpg-XXXXXXXX.pub 2>/dev/null)"

        if [ -z "$tempfile" ]; then
            echoerror "Failed to create temporary file in /tmp"
            return 1
        fi
    else
        tempfile="/tmp/salt-gpg-$$.pub"
    fi

    __fetch_url "$tempfile" "$url" || return 1
    rpm --import "$tempfile" || return 1
    rm -f "$tempfile"

    return 0
}   # ----------  end of function __rpm_import_gpg  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __yum_install_noinput
#   DESCRIPTION:  (DRY) yum install with noinput options
#----------------------------------------------------------------------------------------------------------------------
__yum_install_noinput() {

    ENABLE_EPEL_CMD=""
    # Skip Amazon Linux for the first round, since EPEL is no longer required.
    # See issue #724
    if [ $_DISABLE_REPOS -eq $BS_FALSE ] && [ "$DISTRO_NAME_L" != "amazon_linux_ami" ]; then
        ENABLE_EPEL_CMD="--enablerepo=${_EPEL_REPO}"
    fi

    if [ "$DISTRO_NAME_L" = "oracle_linux" ]; then
        # We need to install one package at a time because --enablerepo=X disables ALL OTHER REPOS!!!!
        for package in "${@}"; do
            yum -y install "${package}" || yum -y install "${package}" ${ENABLE_EPEL_CMD} || return $?
        done
    else
        yum -y install "${@}" ${ENABLE_EPEL_CMD} || return $?
    fi
}   # ----------  end of function __yum_install_noinput  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __git_clone_and_checkout
#   DESCRIPTION:  (DRY) Helper function to clone and checkout salt to a
#                 specific revision.
#----------------------------------------------------------------------------------------------------------------------
__git_clone_and_checkout() {

    echodebug "Installed git version: $(git --version | awk '{ print $3 }')"
    # Turn off SSL verification if -I flag was set for insecure downloads
    if [ "$_INSECURE_DL" -eq $BS_TRUE ]; then
        export GIT_SSL_NO_VERIFY=1
    fi

    case ${OS_NAME_L} in
        openbsd|freebsd|netbsd )
            __TAG_REGEX_MATCH=$(echo "${GIT_REV}" | sed -E 's/^(v?[0-9]{1,4}\.[0-9]{1,2})(\.[0-9]{1,2})?.*$/MATCH/')
            ;;
        * )
            __TAG_REGEX_MATCH=$(echo "${GIT_REV}" | sed 's/^.*\(v\?[[:digit:]]\{1,4\}\.[[:digit:]]\{1,2\}\)\(\.[[:digit:]]\{1,2\}\)\?.*$/MATCH/')
            ;;
    esac

    __SALT_GIT_CHECKOUT_PARENT_DIR=$(dirname "${_SALT_GIT_CHECKOUT_DIR}" 2>/dev/null)
    __SALT_GIT_CHECKOUT_PARENT_DIR="${__SALT_GIT_CHECKOUT_PARENT_DIR:-/tmp/git}"
    __SALT_CHECKOUT_REPONAME="$(basename "${_SALT_GIT_CHECKOUT_DIR}" 2>/dev/null)"
    __SALT_CHECKOUT_REPONAME="${__SALT_CHECKOUT_REPONAME:-salt}"
    [ -d "${__SALT_GIT_CHECKOUT_PARENT_DIR}" ] || mkdir "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
    # shellcheck disable=SC2164
    cd "${__SALT_GIT_CHECKOUT_PARENT_DIR}"
    if [ -d "${_SALT_GIT_CHECKOUT_DIR}" ]; then
        echodebug "Found a checked out Salt repository"
        # shellcheck disable=SC2164
        cd "${_SALT_GIT_CHECKOUT_DIR}"
        echodebug "Fetching git changes"
        git fetch || return 1
        # Tags are needed because of salt's versioning, also fetch that
        echodebug "Fetching git tags"
        git fetch --tags || return 1

        # If we have the SaltStack remote set as upstream, we also need to fetch the tags from there
        if [ "$(git remote -v | grep $_SALTSTACK_REPO_URL)" != "" ]; then
            echodebug "Fetching upstream(SaltStack's Salt repository) git tags"
            git fetch --tags upstream
        else
            echoinfo "Adding SaltStack's Salt repository as a remote"
            git remote add upstream "$_SALTSTACK_REPO_URL"
            echodebug "Fetching upstream(SaltStack's Salt repository) git tags"
            git fetch --tags upstream
        fi

        echodebug "Hard reseting the cloned repository to ${GIT_REV}"
        git reset --hard "$GIT_REV" || return 1

        # Just calling `git reset --hard $GIT_REV` on a branch name that has
        # already been checked out will not update that branch to the upstream
        # HEAD; instead it will simply reset to itself.  Check the ref to see
        # if it is a branch name, check out the branch, and pull in the
        # changes.
        git branch -a | grep -q "${GIT_REV}"
        if [ $? -eq 0 ]; then
            echodebug "Rebasing the cloned repository branch"
            git pull --rebase || return 1
        fi
    else
        if [ "$_FORCE_SHALLOW_CLONE" -eq "${BS_TRUE}" ]; then
            echoinfo "Forced shallow cloning of git repository."
            __SHALLOW_CLONE=$BS_TRUE
        elif [ "$__TAG_REGEX_MATCH" = "MATCH" ]; then
            echoinfo "Git revision matches a Salt version tag, shallow cloning enabled."
            __SHALLOW_CLONE=$BS_TRUE
        else
            echowarn "The git revision being installed does not match a Salt version tag. Shallow cloning disabled"
            __SHALLOW_CLONE=$BS_FALSE
        fi

        if [ "$__SHALLOW_CLONE" -eq $BS_TRUE ]; then
            # Let's try shallow cloning to speed up.
            # Test for "--single-branch" option introduced in git 1.7.10, the minimal version of git where the shallow
            # cloning we need actually works
            if [ "$(git clone 2>&1 | grep 'single-branch')" != "" ]; then
                # The "--single-branch" option is supported, attempt shallow cloning
                echoinfo "Attempting to shallow clone $GIT_REV from Salt's repository ${_SALT_REPO_URL}"
                git clone --depth 1 --branch "$GIT_REV" "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME"
                if [ $? -eq 0 ]; then
                    # shellcheck disable=SC2164
                    cd "${_SALT_GIT_CHECKOUT_DIR}"
                    __SHALLOW_CLONE=$BS_TRUE
                else
                    # Shallow clone above failed(missing upstream tags???), let's resume the old behaviour.
                    echowarn "Failed to shallow clone."
                    echoinfo "Resuming regular git clone and remote SaltStack repository addition procedure"
                    __SHALLOW_CLONE=$BS_FALSE
                fi
            else
                echodebug "Shallow cloning not possible. Required git version not met."
                __SHALLOW_CLONE=$BS_FALSE
            fi
        fi

        if [ "$__SHALLOW_CLONE" -eq $BS_FALSE ]; then
            git clone "$_SALT_REPO_URL" "$__SALT_CHECKOUT_REPONAME" || return 1
            # shellcheck disable=SC2164
            cd "${_SALT_GIT_CHECKOUT_DIR}"

            if ! echo "$_SALT_REPO_URL" | grep -q -F -w "${_SALTSTACK_REPO_URL#*://}"; then
                # We need to add the saltstack repository as a remote and fetch tags for proper versioning
                echoinfo "Adding SaltStack's Salt repository as a remote"
                git remote add upstream "$_SALTSTACK_REPO_URL" || return 1

                echodebug "Fetching upstream (SaltStack's Salt repository) git tags"
                git fetch --tags upstream || return 1

                # Check if GIT_REV is a remote branch or just a commit hash
                if git branch -r | grep -q -F -w "origin/$GIT_REV"; then
                    GIT_REV="origin/$GIT_REV"
                fi
            fi

            echodebug "Checking out $GIT_REV"
            git checkout "$GIT_REV" || return 1
        fi

    fi

    echoinfo "Cloning Salt's git repository succeeded"
    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __copyfile
#   DESCRIPTION:  Simple function to copy files. Overrides if asked.
#----------------------------------------------------------------------------------------------------------------------
__copyfile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        sfile=$1
        dfile=$2
    elif [ $# -eq 3 ]; then
        sfile=$1
        dfile=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for __copyfile()"
        echoinfo "USAGE: __copyfile <source> <dest>  OR  __copyfile <source> <dest> <overwrite>"
        exit 1
    fi

    # Does the source file exist?
    if [ ! -f "$sfile" ]; then
        echowarn "$sfile does not exist!"
        return 1
    fi

    # If the destination is a directory, let's make it a full path so the logic
    # below works as expected
    if [ -d "$dfile" ]; then
        echodebug "The passed destination ($dfile) is a directory"
        dfile="${dfile}/$(basename "$sfile")"
        echodebug "Full destination path is now: $dfile"
    fi

    if [ ! -f "$dfile" ]; then
        # The destination file does not exist, copy
        echodebug "Copying $sfile to $dfile"
        cp "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -eq $BS_TRUE ]; then
        # The destination exist and we're overwriting
        echodebug "Overwriting $dfile with $sfile"
        cp -f "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -ne $BS_TRUE ]; then
        echodebug "Not overwriting $dfile with $sfile"
    fi
    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __movefile
#   DESCRIPTION:  Simple function to move files. Overrides if asked.
#----------------------------------------------------------------------------------------------------------------------
__movefile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        sfile=$1
        dfile=$2
    elif [ $# -eq 3 ]; then
        sfile=$1
        dfile=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for __movefile()"
        echoinfo "USAGE: __movefile <source> <dest>  OR  __movefile <source> <dest> <overwrite>"
        exit 1
    fi

    if [ $_KEEP_TEMP_FILES -eq $BS_TRUE ]; then
        # We're being told not to move files, instead copy them so we can keep
        # them around
        echodebug "Since BS_KEEP_TEMP_FILES=1 we're copying files instead of moving them"
        __copyfile "$sfile" "$dfile" "$overwrite"
        return $?
    fi

    # Does the source file exist?
    if [ ! -f "$sfile" ]; then
        echowarn "$sfile does not exist!"
        return 1
    fi

    # If the destination is a directory, let's make it a full path so the logic
    # below works as expected
    if [ -d "$dfile" ]; then
        echodebug "The passed destination($dfile) is a directory"
        dfile="${dfile}/$(basename "$sfile")"
        echodebug "Full destination path is now: $dfile"
    fi

    if [ ! -f "$dfile" ]; then
        # The destination file does not exist, move
        echodebug "Moving $sfile to $dfile"
        mv "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -eq $BS_TRUE ]; then
        # The destination exist and we're overwriting
        echodebug "Overriding $dfile with $sfile"
        mv -f "$sfile" "$dfile" || return 1
    elif [ -f "$dfile" ] && [ "$overwrite" -ne $BS_TRUE ]; then
        echodebug "Not overriding $dfile with $sfile"
    fi

    return 0
}


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __linkfile
#   DESCRIPTION:  Simple function to create symlinks. Overrides if asked. Accepts globs.
#----------------------------------------------------------------------------------------------------------------------
__linkfile() {
    overwrite=$_FORCE_OVERWRITE
    if [ $# -eq 2 ]; then
        target=$1
        linkname=$2
    elif [ $# -eq 3 ]; then
        target=$1
        linkname=$2
        overwrite=$3
    else
        echoerror "Wrong number of arguments for __linkfile()"
        echoinfo "USAGE: __linkfile <target> <link>  OR  __linkfile <tagret> <link> <overwrite>"
        exit 1
    fi

    for sfile in $target; do
        # Does the source file exist?
        if [ ! -f "$sfile" ]; then
            echowarn "$sfile does not exist!"
            return 1
        fi

        # If the destination is a directory, let's make it a full path so the logic
        # below works as expected
        if [ -d "$linkname" ]; then
            echodebug "The passed link name ($linkname) is a directory"
            linkname="${linkname}/$(basename "$sfile")"
            echodebug "Full destination path is now: $linkname"
        fi

        if [ ! -e "$linkname" ]; then
            # The destination file does not exist, create link
            echodebug "Creating $linkname symlink pointing to $sfile"
            ln -s "$sfile" "$linkname" || return 1
        elif [ -e "$linkname" ] && [ "$overwrite" -eq $BS_TRUE ]; then
            # The destination exist and we're overwriting
            echodebug "Overwriting $linkname symlink to point on $sfile"
            ln -sf "$sfile" "$linkname" || return 1
        elif [ -e "$linkname" ] && [ "$overwrite" -ne $BS_TRUE ]; then
            echodebug "Not overwriting $linkname symlink to point on $sfile"
        fi
    done

    return 0
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __overwriteconfig()
#   DESCRIPTION:  Simple function to overwrite master or minion config files.
#----------------------------------------------------------------------------------------------------------------------
__overwriteconfig() {
    if [ $# -eq 2 ]; then
        target=$1
        json=$2
    else
        echoerror "Wrong number of arguments for __convert_json_to_yaml_str()"
        echoinfo "USAGE: __convert_json_to_yaml_str <configfile> <jsonstring>"
        exit 1
    fi

    # Make a tempfile to dump any python errors into.
    if __check_command_exists mktemp; then
        tempfile="$(mktemp /tmp/salt-config-XXXXXXXX 2>/dev/null)"

        if [ -z "$tempfile" ]; then
            echoerror "Failed to create temporary file in /tmp"
            return 1
        fi
    else
        tempfile="/tmp/salt-config-$$"
    fi

    # If python does not have yaml installed we're on Arch and should use python2
    if python -c "import yaml" 2> /dev/null; then
        good_python=python
    else
        good_python=python2
    fi

    # Convert json string to a yaml string and write it to config file. Output is dumped into tempfile.
    $good_python -c "import json; import yaml; jsn=json.loads('$json'); yml=yaml.safe_dump(jsn, line_break='\n', default_flow_style=False); config_file=open('$target', 'w'); config_file.write(yml); config_file.close();" 2>$tempfile

    # No python errors output to the tempfile
    if [ ! -s "$tempfile" ]; then
        rm -f "$tempfile"
        return 0
    fi

    # Errors are present in the tempfile - let's expose them to the user.
    fullerror=$(cat "$tempfile")
    echodebug "$fullerror"
    echoerror "Python error encountered. This is likely due to passing in a malformed JSON string. Please use -D to see stacktrace."

    rm -f "$tempfile"

    return 1

}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_systemd
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_systemd() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    if [ "$(systemctl is-enabled "${servicename}")" = "enabled" ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_systemd  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_upstart
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_upstart() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # Check if service is enabled to start at boot
    initctl list | grep "${servicename}" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_upstart  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_sysvinit
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_sysvinit() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    if [ "$(LC_ALL=C /sbin/chkconfig --list | grep "\<${servicename}\>" | grep '[2-5]:on')" != "" ]; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_sysvinit  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_debian
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_debian() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # Check if the service is going to be started at any runlevel, fixes bootstrap in container (Docker, LXC)
    if ls /etc/rc?.d/S*"${servicename}" >/dev/null 2>&1; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_debian  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_openbsd
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_openbsd() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # shellcheck disable=SC2086,SC2046,SC2144
    if rcctl get ${servicename} status; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_openbsd  ----------

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __check_services_alpine
#   DESCRIPTION:  Return 0 or 1 in case the service is enabled or not
#    PARAMETERS:  servicename
#----------------------------------------------------------------------------------------------------------------------
__check_services_alpine() {
    if [ $# -eq 0 ]; then
        echoerror "You need to pass a service name to check!"
        exit 1
    elif [ $# -ne 1 ]; then
        echoerror "You need to pass a service name to check as the single argument to the function"
    fi

    servicename=$1
    echodebug "Checking if service ${servicename} is enabled"

    # shellcheck disable=SC2086,SC2046,SC2144
    if rc-status $(rc-status -r) | tail -n +2 | grep -q "\<$servicename\>"; then
        echodebug "Service ${servicename} is enabled"
        return 0
    else
        echodebug "Service ${servicename} is NOT enabled"
        return 1
    fi
}   # ----------  end of function __check_services_openbsd  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __create_virtualenv
#   DESCRIPTION:  Return 0 or 1 depending on successful creation of virtualenv
#----------------------------------------------------------------------------------------------------------------------
__create_virtualenv() {
    if [ ! -d "$_VIRTUALENV_DIR" ]; then
        echoinfo "Creating virtualenv ${_VIRTUALENV_DIR}"
        if [ $_PIP_ALL -eq $BS_TRUE ]; then
            virtualenv --no-site-packages "${_VIRTUALENV_DIR}" || return 1
        else
            virtualenv --system-site-packages "${_VIRTUALENV_DIR}" || return 1
        fi
    fi
    return 0
}   # ----------  end of function __create_virtualenv  ----------


#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __activate_virtualenv
#   DESCRIPTION:  Return 0 or 1 depending on successful activation of virtualenv
#----------------------------------------------------------------------------------------------------------------------
__activate_virtualenv() {
    set +o nounset
    # Is virtualenv empty
    if [ -z "$VIRTUAL_ENV" ]; then
        __create_virtualenv || return 1
        # shellcheck source=/dev/null
        . "${_VIRTUALENV_DIR}/bin/activate" || return 1
        echoinfo "Activated virtualenv ${_VIRTUALENV_DIR}"
    fi
    set -o nounset
    return 0
}   # ----------  end of function __activate_virtualenv  ----------

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __install_pip_pkgs
#   DESCRIPTION:  Return 0 or 1 if successfully able to install pip packages. Can provide a different python version to
#                 install pip packages with. If $py_ver is not specified it will use the default python version.
#    PARAMETERS:  pkgs, py_ver
#----------------------------------------------------------------------------------------------------------------------

__install_pip_pkgs() {
    _pip_pkgs="$1"
    _py_exe="$2"
    _py_pkg=$(echo "$_py_exe" | sed -r "s/\.//g")
    _pip_cmd="${_py_exe} -m pip"

    if [ "${_py_exe}" = "" ]; then
        _py_exe='python'
    fi

    __check_pip_allowed

    # Install pip and pip dependencies
    if ! __check_command_exists "${_pip_cmd} --version"; then
        __PACKAGES="${_py_pkg}-setuptools ${_py_pkg}-pip gcc ${_py_pkg}-devel"
        # shellcheck disable=SC2086
        __yum_install_noinput ${__PACKAGES} || return 1
    fi

    echoinfo "Installing pip packages: ${_pip_pkgs} using ${_py_exe}"
    # shellcheck disable=SC2086
    ${_pip_cmd} install ${_pip_pkgs} || return 1
}

#---  FUNCTION  -------------------------------------------------------------------------------------------------------
#          NAME:  __install_pip_deps
#   DESCRIPTION:  Return 0 or 1 if successfully able to install pip packages via requirements file
#    PARAMETERS:  requirements_file
#----------------------------------------------------------------------------------------------------------------------
__install_pip_deps() {
    # Install virtualenv to system pip before activating virtualenv if thats going to be used
    # We assume pip pkg is installed since that is distro specific
    if [ "$_VIRTUALENV_DIR" != "null" ]; then
        if ! __check_command_exists pip; then
            echoerror "Pip not installed: required for -a installs"
            exit 1
        fi
        pip install -U virtualenv
        __activate_virtualenv || return 1
    else
        echoerror "Must have virtualenv dir specified for -a installs"
    fi

    requirements_file=$1
    if [ ! -f "${requirements_file}" ]; then
        echoerror "Requirements file: ${requirements_file} cannot be found, needed for -a (pip pkg) installs"
        exit 1
    fi

    __PIP_PACKAGES=''
    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # shellcheck disable=SC2089
        __PIP_PACKAGES="${__PIP_PACKAGES} 'apache-libcloud>=$_LIBCLOUD_MIN_VERSION'"
    fi

    # shellcheck disable=SC2086,SC2090
    pip install -U -r ${requirements_file} ${__PIP_PACKAGES}
}   # ----------  end of function __install_pip_deps  ----------


#######################################################################################################################
#
#   Distribution install functions
#
#   In order to install salt for a distribution you need to define:
#
#   To Install Dependencies, which is required, one of:
#       1. install_<distro>_<major_version>_<install_type>_deps
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_deps
#       3. install_<distro>_<major_version>_deps
#       4  install_<distro>_<major_version>_<minor_version>_deps
#       5. install_<distro>_<install_type>_deps
#       6. install_<distro>_deps
#
#   Optionally, define a salt configuration function, which will be called if
#   the -c (config-dir) option is passed. One of:
#       1. config_<distro>_<major_version>_<install_type>_salt
#       2. config_<distro>_<major_version>_<minor_version>_<install_type>_salt
#       3. config_<distro>_<major_version>_salt
#       4  config_<distro>_<major_version>_<minor_version>_salt
#       5. config_<distro>_<install_type>_salt
#       6. config_<distro>_salt
#       7. config_salt [THIS ONE IS ALREADY DEFINED AS THE DEFAULT]
#
#   Optionally, define a salt master pre-seed function, which will be called if
#   the -k (pre-seed master keys) option is passed. One of:
#       1. preseed_<distro>_<major_version>_<install_type>_master
#       2. preseed_<distro>_<major_version>_<minor_version>_<install_type>_master
#       3. preseed_<distro>_<major_version>_master
#       4  preseed_<distro>_<major_version>_<minor_version>_master
#       5. preseed_<distro>_<install_type>_master
#       6. preseed_<distro>_master
#       7. preseed_master [THIS ONE IS ALREADY DEFINED AS THE DEFAULT]
#
#   To install salt, which, of course, is required, one of:
#       1. install_<distro>_<major_version>_<install_type>
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>
#       3. install_<distro>_<install_type>
#
#   Optionally, define a post install function, one of:
#       1. install_<distro>_<major_version>_<install_type>_post
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_post
#       3. install_<distro>_<major_version>_post
#       4  install_<distro>_<major_version>_<minor_version>_post
#       5. install_<distro>_<install_type>_post
#       6. install_<distro>_post
#
#   Optionally, define a start daemons function, one of:
#       1. install_<distro>_<major_version>_<install_type>_restart_daemons
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_restart_daemons
#       3. install_<distro>_<major_version>_restart_daemons
#       4  install_<distro>_<major_version>_<minor_version>_restart_daemons
#       5. install_<distro>_<install_type>_restart_daemons
#       6. install_<distro>_restart_daemons
#
#       NOTE: The start daemons function should be able to restart any daemons
#             which are running, or start if they're not running.
#
#   Optionally, define a daemons running function, one of:
#       1. daemons_running_<distro>_<major_version>_<install_type>
#       2. daemons_running_<distro>_<major_version>_<minor_version>_<install_type>
#       3. daemons_running_<distro>_<major_version>
#       4  daemons_running_<distro>_<major_version>_<minor_version>
#       5. daemons_running_<distro>_<install_type>
#       6. daemons_running_<distro>
#       7. daemons_running  [THIS ONE IS ALREADY DEFINED AS THE DEFAULT]
#
#   Optionally, check enabled Services:
#       1. install_<distro>_<major_version>_<install_type>_check_services
#       2. install_<distro>_<major_version>_<minor_version>_<install_type>_check_services
#       3. install_<distro>_<major_version>_check_services
#       4  install_<distro>_<major_version>_<minor_version>_check_services
#       5. install_<distro>_<install_type>_check_services
#       6. install_<distro>_check_services
#
#######################################################################################################################


#######################################################################################################################
#
#   Ubuntu Install Functions
#
__enable_universe_repository() {
    if [ "$(grep -R universe /etc/apt/sources.list /etc/apt/sources.list.d/ | grep -v '#')" != "" ]; then
        # The universe repository is already enabled
        return 0
    fi

    echodebug "Enabling the universe repository"

    add-apt-repository -y "deb http://archive.ubuntu.com/ubuntu $(lsb_release -sc) universe" || return 1

    return 0
}

__install_saltstack_ubuntu_repository() {
    # Workaround for latest non-LTS ubuntu
    if [ "$DISTRO_VERSION" = "16.10" ] || [ "$DISTRO_MAJOR_VERSION" -gt 16 ]; then
        echowarn "Non-LTS Ubuntu detected, but stable packages requested. Trying packages from latest LTS release. You may experience problems."
        UBUNTU_VERSION=16.04
        UBUNTU_CODENAME="xenial"
    else
        UBUNTU_VERSION=$DISTRO_VERSION
        UBUNTU_CODENAME=$DISTRO_CODENAME
    fi

    __PACKAGES=''

    # Install downloader backend for GPG keys fetching
    if [ "$DISTRO_VERSION" = "16.10" ] || [ "$DISTRO_MAJOR_VERSION" -gt 16 ]; then
        __PACKAGES="${__PACKAGES} gnupg2 dirmngr"
    else
        __PACKAGES="${__PACKAGES} gnupg-curl"
    fi

    # Make sure https transport is available
    if [ "$HTTP_VAL" = "https" ] ; then
        __PACKAGES="${__PACKAGES} apt-transport-https ca-certificates"
    fi

    # shellcheck disable=SC2086,SC2090
    __apt_get_install_noinput ${__PACKAGES} || return 1

    # SaltStack's stable Ubuntu repository:
    SALTSTACK_UBUNTU_URL="${HTTP_VAL}://${_REPO_URL}/apt/ubuntu/${UBUNTU_VERSION}/${__REPO_ARCH}/${STABLE_REV}"
    echo "deb $SALTSTACK_UBUNTU_URL $UBUNTU_CODENAME main" > /etc/apt/sources.list.d/saltstack.list

    __apt_key_fetch "$SALTSTACK_UBUNTU_URL/SALTSTACK-GPG-KEY.pub" || return 1

    apt-get update
}

install_ubuntu_deps() {
    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Install add-apt-repository
        if ! __check_command_exists add-apt-repository; then
            __apt_get_install_noinput software-properties-common || return 1
        fi

        __enable_universe_repository || return 1

        apt-get update
    fi

    __PACKAGES=''

    if [ "$DISTRO_MAJOR_VERSION" -lt 16 ]; then
        # Minimal systems might not have upstart installed, install it
        __PACKAGES="upstart"
    fi

    if [ "$DISTRO_MAJOR_VERSION" -ge 16 ]; then
        __PACKAGES="${__PACKAGES} python2.7"
    fi

    if [ "$_VIRTUALENV_DIR" != "null" ]; then
        __PACKAGES="${__PACKAGES} python-virtualenv"
    fi
    # Need python-apt for managing packages via Salt
    __PACKAGES="${__PACKAGES} python-apt"

    # requests is still used by many salt modules
    __PACKAGES="${__PACKAGES} python-requests"

    # YAML module is used for generating custom master/minion configs
    __PACKAGES="${__PACKAGES} python-yaml"

    # Additionally install procps and pciutils which allows for Docker bootstraps. See 366#issuecomment-39666813
    __PACKAGES="${__PACKAGES} procps pciutils"

    # shellcheck disable=SC2086,SC2090
    __apt_get_install_noinput ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_ubuntu_stable_deps() {
    if [ "${_SLEEP}" -eq "${__DEFAULT_SLEEP}" ] && [ "$DISTRO_MAJOR_VERSION" -lt 16 ]; then
        # The user did not pass a custom sleep value as an argument, let's increase the default value
        echodebug "On Ubuntu systems we increase the default sleep value to 10."
        echodebug "See https://github.com/saltstack/salt/issues/12248 for more info."
        _SLEEP=10
    fi

    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi

    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    if [ "${_UPGRADE_SYS}" -eq $BS_TRUE ]; then
        if [ "${_INSECURE_DL}" -eq $BS_TRUE ]; then
            __apt_get_install_noinput --allow-unauthenticated debian-archive-keyring &&
                apt-key update && apt-get update
        fi

        __apt_get_upgrade_noinput || return 1
    fi

    if [ "$_DISABLE_REPOS" -eq "$BS_FALSE" ] || [ "$_CUSTOM_REPO_URL" != "null" ]; then
        __check_dpkg_architecture || return 1
        __install_saltstack_ubuntu_repository || return 1
    fi

    install_ubuntu_deps || return 1
}

install_ubuntu_daily_deps() {
    install_ubuntu_stable_deps || return 1

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        __enable_universe_repository || return 1

        add-apt-repository -y ppa:saltstack/salt-daily || return 1
        apt-get update
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __apt_get_upgrade_noinput || return 1
    fi

    return 0
}

install_ubuntu_git_deps() {
    apt-get update

    if ! __check_command_exists git; then
        __apt_get_install_noinput git-core || return 1
    fi

    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        __apt_get_install_noinput ca-certificates
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES=""

    # See how we are installing packages
    if [ "${_PIP_ALL}" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-dev swig libssl-dev libzmq3 libzmq3-dev"

        if ! __check_command_exists pip; then
            __PACKAGES="${__PACKAGES} python-setuptools python-pip"
        fi

        # Get just the apt packages that are required to build all the pythons
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${__PACKAGES} || return 1
        # Install the pythons from requirements (only zmq for now)
        __install_pip_deps "${_SALT_GIT_CHECKOUT_DIR}/requirements/zeromq.txt" || return 1
    else
        install_ubuntu_stable_deps || return 1

        __PACKAGES="${__PACKAGES} python-crypto python-jinja2 python-msgpack python-requests"
        __PACKAGES="${__PACKAGES} python-tornado python-yaml python-zmq"

        if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
            # Install python-libcloud if asked to
            __PACKAGES="${__PACKAGES} python-libcloud"
        fi

        # shellcheck disable=SC2086
        __apt_get_install_noinput ${__PACKAGES} || return 1
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_ubuntu_stable() {
    __PACKAGES=""

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-cloud"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    return 0
}

install_ubuntu_daily() {
    install_ubuntu_stable || return 1

    return 0
}

install_ubuntu_git() {
    # Activate virtualenv before install
    if [ "${_VIRTUALENV_DIR}" != "null" ]; then
        __activate_virtualenv || return 1
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install --install-layout=deb || return 1
    else
        python setup.py ${SETUP_PY_INSTALL_ARGS} install --install-layout=deb || return 1
    fi

    return 0
}

install_ubuntu_stable_post() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            # Using systemd
            /bin/systemctl is-enabled salt-$fname.service > /dev/null 2>&1 || (
                /bin/systemctl preset salt-$fname.service > /dev/null 2>&1 &&
                /bin/systemctl enable salt-$fname.service > /dev/null 2>&1
            )
            sleep 0.1
            /bin/systemctl daemon-reload
        elif [ -f /etc/init.d/salt-$fname ]; then
            update-rc.d salt-$fname defaults
        fi
    done

    return 0
}

install_ubuntu_git_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 16 ]; then
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
            sleep 0.1
            systemctl daemon-reload
        elif [ -f /sbin/initctl ]; then
            _upstart_conf="/etc/init/salt-$fname.conf"
            # We have upstart support
            echodebug "There's upstart support"
            if [ ! -f $_upstart_conf ]; then
                # upstart does not know about our service, let's copy the proper file
                echowarn "Upstart does not appear to know about salt-$fname"
                echodebug "Copying ${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-$fname.upstart to $_upstart_conf"
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.upstart" "$_upstart_conf"
                # Set service to know about virtualenv
                if [ "${_VIRTUALENV_DIR}" != "null" ]; then
                    echo "SALT_USE_VIRTUALENV=${_VIRTUALENV_DIR}" > /etc/default/salt-${fname}
                fi
                /sbin/initctl reload-configuration || return 1
            fi
        # No upstart support in Ubuntu!?
        elif [ -f "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.init" ]; then
            echodebug "There's NO upstart support!?"
            echodebug "Copying ${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.init to /etc/init.d/salt-$fname"
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.init" "/etc/init.d/salt-$fname"
            chmod +x /etc/init.d/salt-$fname

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            update-rc.d salt-$fname defaults
        else
            echoerror "Neither upstart nor init.d was setup for salt-$fname"
        fi
    done

    return 0
}

install_ubuntu_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    # Ensure upstart configs / systemd units are loaded
    if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 16 ]; then
        systemctl daemon-reload
    elif [ -f /sbin/initctl ]; then
        /sbin/initctl reload-configuration
    fi

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 16 ]; then
            echodebug "There's systemd support while checking salt-$fname"
            systemctl stop salt-$fname > /dev/null 2>&1
            systemctl start salt-$fname.service
            [ $? -eq 0 ] && continue
            # We failed to start the service, let's test the SysV code below
            echodebug "Failed to start salt-$fname using systemd"
        fi

        if [ -f /sbin/initctl ]; then
            echodebug "There's upstart support while checking salt-$fname"

            status salt-$fname 2>/dev/null | grep -q running
            if [ $? -eq 0 ]; then
                stop salt-$fname || (echodebug "Failed to stop salt-$fname" && return 1)
            fi

            start salt-$fname
            [ $? -eq 0 ] && continue
            # We failed to start the service, let's test the SysV code below
            echodebug "Failed to start salt-$fname using Upstart"
        fi

        if [ ! -f /etc/init.d/salt-$fname ]; then
            echoerror "No init.d support for salt-$fname was found"
            return 1
        fi

        /etc/init.d/salt-$fname stop > /dev/null 2>&1
        /etc/init.d/salt-$fname start
    done

    return 0
}

install_ubuntu_check_services() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ] && [ "$DISTRO_MAJOR_VERSION" -ge 16 ]; then
            __check_services_systemd salt-$fname || return 1
        elif [ -f /sbin/initctl ] && [ -f /etc/init/salt-${fname}.conf ]; then
            __check_services_upstart salt-$fname || return 1
        elif [ -f /etc/init.d/salt-$fname ]; then
            __check_services_debian salt-$fname || return 1
        fi
    done

    return 0
}
#
#   End of Ubuntu Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Debian Install Functions
#
__install_saltstack_debian_repository() {
    if [ "$DISTRO_MAJOR_VERSION" -eq 10 ]; then
        # Packages for Debian 10 at repo.saltstack.com are not yet available
        # Set up repository for Debian 9 for Debian 10 for now until support
        # is available at repo.saltstack.com for Debian 10.
        echowarn "Debian 10 distribution detected, but stable packages requested. Trying packages from Debian 9. You may experience problems."
        DEBIAN_RELEASE="9"
        DEBIAN_CODENAME="stretch"
    else
        DEBIAN_RELEASE="$DISTRO_MAJOR_VERSION"
        DEBIAN_CODENAME="$DISTRO_CODENAME"
    fi

    __PACKAGES=''

    # Install downloader backend for GPG keys fetching
    if [ "$DISTRO_MAJOR_VERSION" -ge 9 ]; then
        __PACKAGES="${__PACKAGES} gnupg2 dirmngr"
    else
        __PACKAGES="${__PACKAGES} gnupg-curl"
    fi

    # Make sure https transport is available
    if [ "$HTTP_VAL" = "https" ] ; then
        __PACKAGES="${__PACKAGES} apt-transport-https ca-certificates"
    fi

    # shellcheck disable=SC2086,SC2090
    __apt_get_install_noinput ${__PACKAGES} || return 1

    # amd64 is just a part of repository URI, 32-bit pkgs are hosted under the same location
    SALTSTACK_DEBIAN_URL="${HTTP_VAL}://${_REPO_URL}/apt/debian/${DEBIAN_RELEASE}/${__REPO_ARCH}/${STABLE_REV}"
    echo "deb $SALTSTACK_DEBIAN_URL $DEBIAN_CODENAME main" > "/etc/apt/sources.list.d/saltstack.list"

    __apt_key_fetch "$SALTSTACK_DEBIAN_URL/SALTSTACK-GPG-KEY.pub" || return 1

    apt-get update
}

install_debian_deps() {
    if [ $_START_DAEMONS -eq $BS_FALSE ]; then
        echowarn "Not starting daemons on Debian based distributions is not working mostly because starting them is the default behaviour."
    fi

    # No user interaction, libc6 restart services for example
    export DEBIAN_FRONTEND=noninteractive

    apt-get update

    if [ "${_UPGRADE_SYS}" -eq $BS_TRUE ]; then
        # Try to update GPG keys first if allowed
        if [ "${_INSECURE_DL}" -eq $BS_TRUE ]; then
            __apt_get_install_noinput --allow-unauthenticated debian-archive-keyring &&
                apt-key update && apt-get update
        fi

        __apt_get_upgrade_noinput || return 1
    fi

    # Additionally install procps and pciutils which allows for Docker bootstraps. See 366#issuecomment-39666813
    __PACKAGES='procps pciutils'

    # YAML module is used for generating custom master/minion configs
    __PACKAGES="${__PACKAGES} python-yaml"

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    if [ "$_DISABLE_REPOS" -eq "$BS_FALSE" ] || [ "$_CUSTOM_REPO_URL" != "null" ]; then
        __check_dpkg_architecture || return 1
        __install_saltstack_debian_repository || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __apt_get_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_debian_git_deps() {
    if ! __check_command_exists git; then
        __apt_get_install_noinput git || return 1
    fi

    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        __apt_get_install_noinput ca-certificates
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES="libzmq3 libzmq3-dev lsb-release python-apt python-backports.ssl-match-hostname python-crypto"
    __PACKAGES="${__PACKAGES} python-jinja2 python-msgpack python-requests"
    __PACKAGES="${__PACKAGES} python-tornado python-yaml python-zmq"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # Install python-libcloud if asked to
        __PACKAGES="${__PACKAGES} python-libcloud"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_debian_7_git_deps() {
    install_debian_deps || return 1
    install_debian_git_deps || return 1

    return 0
}

install_debian_8_git_deps() {
    install_debian_deps || return 1

    if ! __check_command_exists git; then
        __apt_get_install_noinput git || return 1
    fi

    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        __apt_get_install_noinput ca-certificates
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES="libzmq3 libzmq3-dev lsb-release python-apt python-crypto python-jinja2 python-msgpack"
    __PACKAGES="${__PACKAGES} python-requests python-systemd python-yaml python-zmq"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # Install python-libcloud if asked to
        __PACKAGES="${__PACKAGES} python-libcloud"
    fi

    __PIP_PACKAGES=''
    if (__check_pip_allowed >/dev/null 2>&1); then
        __PIP_PACKAGES='tornado'
        # Install development environment for building tornado Python module
        __PACKAGES="${__PACKAGES} build-essential python-dev"

        if ! __check_command_exists pip; then
            __PACKAGES="${__PACKAGES} python-pip"
        fi
    # Attempt to configure backports repo on non-x86_64 system
    elif [ $_DISABLE_REPOS -eq $BS_FALSE ] && [ "$DPKG_ARCHITECTURE" != "amd64" ]; then
        # Check if Debian Backports repo already configured
        if ! apt-cache policy | grep -q 'Debian Backports'; then
            echo 'deb http://httpredir.debian.org/debian jessie-backports main' > \
                /etc/apt/sources.list.d/backports.list
        fi

        apt-get update || return 1

        # python-tornado package should be installed from backports repo
        __PACKAGES="${__PACKAGES} python-backports.ssl-match-hostname python-tornado/jessie-backports"
    else
        __PACKAGES="${__PACKAGES} python-backports.ssl-match-hostname python-tornado"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    if [ "${__PIP_PACKAGES}" != "" ]; then
        # shellcheck disable=SC2086,SC2090
        pip install -U ${__PIP_PACKAGES} || return 1
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_debian_9_git_deps() {
    install_debian_deps || return 1

    if ! __check_command_exists git; then
        __apt_get_install_noinput git || return 1
    fi

    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        __apt_get_install_noinput ca-certificates
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES="libzmq5 lsb-release python-apt python-backports-abc python-crypto"
    __PACKAGES="${__PACKAGES} python-jinja2 python-msgpack python-requests python-systemd"
    __PACKAGES="${__PACKAGES} python-tornado python-yaml python-zmq"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # Install python-libcloud if asked to
        __PACKAGES="${__PACKAGES} python-libcloud"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_debian_10_git_deps() {
    install_debian_9_git_deps || return 1
    return 0
}

install_debian_stable() {
    __PACKAGES=""

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-cloud"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    # shellcheck disable=SC2086
    __apt_get_install_noinput ${__PACKAGES} || return 1

    return 0
}

install_debian_7_stable() {
    install_debian_stable || return 1
    return 0
}

install_debian_8_stable() {
    install_debian_stable || return 1
    return 0
}

install_debian_9_stable() {
    install_debian_stable || return 1
    return 0
}

install_debian_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install --install-layout=deb || return 1
    else
        python setup.py ${SETUP_PY_INSTALL_ARGS} install --install-layout=deb || return 1
    fi
}

install_debian_7_git() {
    install_debian_git || return 1
    return 0
}

install_debian_8_git() {
    install_debian_git || return 1
    return 0
}

install_debian_9_git() {
    install_debian_git || return 1
    return 0
}

install_debian_git_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ "$fname" = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ "$fname" = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ "$fname" = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ "$fname" = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Configure SystemD for Debian 8 "Jessie" and later
        if [ -f /bin/systemctl ]; then
            if [ ! -f /lib/systemd/system/salt-${fname}.service ] || \
                ([ -f /lib/systemd/system/salt-${fname}.service ] && [ $_FORCE_OVERWRITE -eq $BS_TRUE ]); then
                if [ -f "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" ]; then
                    __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" /lib/systemd/system
                    __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.environment" "/etc/default/salt-${fname}"
                else
                    # workaround before adding Debian-specific unit files to the Salt main repo
                    __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" /lib/systemd/system
                    sed -i -e '/^Type/ s/notify/simple/' /lib/systemd/system/salt-${fname}.service
                fi
            fi

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ "$fname" = "api" ] && continue

            /bin/systemctl enable "salt-${fname}.service"
            SYSTEMD_RELOAD=$BS_TRUE

        # Install initscripts for Debian 7 "Wheezy"
        elif [ ! -f "/etc/init.d/salt-$fname" ] || \
            ([ -f "/etc/init.d/salt-$fname" ] && [ "$_FORCE_OVERWRITE" -eq $BS_TRUE ]); then
            if [ -f "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-$fname.init" ]; then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.init" "/etc/init.d/salt-${fname}"
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.environment" "/etc/default/salt-${fname}"
            else
                # Make sure wget is available
                __check_command_exists wget || __apt_get_install_noinput wget || return 1
                __fetch_url "/etc/init.d/salt-${fname}" "${HTTP_VAL}://anonscm.debian.org/cgit/pkg-salt/salt.git/plain/debian/salt-${fname}.init"
            fi

            if [ ! -f "/etc/init.d/salt-${fname}" ]; then
                echowarn "The init script for salt-${fname} was not found, skipping it..."
                continue
            fi

            chmod +x "/etc/init.d/salt-${fname}"

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ "$fname" = "api" ] && continue

            update-rc.d "salt-${fname}" defaults
        fi
    done
}

install_debian_restart_daemons() {
    [ "$_START_DAEMONS" -eq $BS_FALSE ] && return 0

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            # Debian 8 uses systemd
            /bin/systemctl stop salt-$fname > /dev/null 2>&1
            /bin/systemctl start salt-$fname.service
        elif [ -f /etc/init.d/salt-$fname ]; then
            # Still in SysV init
            /etc/init.d/salt-$fname stop > /dev/null 2>&1
            /etc/init.d/salt-$fname start
        fi
    done
}

install_debian_check_services() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            __check_services_systemd salt-$fname || return 1
        elif [ -f /etc/init.d/salt-$fname ]; then
            __check_services_debian salt-$fname || return 1
        fi
    done
    return 0
}
#
#   Ended Debian Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Fedora Install Functions
#

install_fedora_deps() {

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        if [ "$_ENABLE_EXTERNAL_ZMQ_REPOS" -eq $BS_TRUE ]; then
            __install_saltstack_copr_zeromq_repository || return 1
        fi

        __install_saltstack_copr_salt_repository || return 1
    fi

    __PACKAGES="PyYAML libyaml python-crypto python-jinja2 python-zmq python2-msgpack python2-requests"

    if [ "$DISTRO_MAJOR_VERSION" -lt 26 ]; then
        __PACKAGES="${__PACKAGES} yum-utils"
    else
        __PACKAGES="${__PACKAGES} dnf-utils"
    fi

    # shellcheck disable=SC2086
    dnf install -y ${__PACKAGES} || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        dnf -y update || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        dnf install -y ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_fedora_stable() {
    __PACKAGES=""

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-cloud"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    # shellcheck disable=SC2086
    dnf install -y ${__PACKAGES} || return 1

    return 0
}

install_fedora_stable_post() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
        sleep 0.1
        systemctl daemon-reload
    done
}

install_fedora_git_deps() {

    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        dnf install -y ca-certificates || return 1
    fi

    install_fedora_deps || return 1

    if ! __check_command_exists git; then
        dnf install -y git || return 1
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES="python2-tornado systemd-python"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-libcloud python-netaddr"
    fi

    # shellcheck disable=SC2086
    dnf install -y ${__PACKAGES} || return 1

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_fedora_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install || return 1
    else
        python setup.py ${SETUP_PY_INSTALL_ARGS} install || return 1
    fi
    return 0
}

install_fedora_git_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
        sleep 0.1
        systemctl daemon-reload
    done
}

install_fedora_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        systemctl stop salt-$fname > /dev/null 2>&1
        systemctl start salt-$fname.service
    done
}

install_fedora_check_services() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __check_services_systemd salt-$fname || return 1
    done

    return 0
}
#
#   Ended Fedora Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   CentOS Install Functions
#
__install_epel_repository() {
    if [ ${_EPEL_REPOS_INSTALLED} -eq $BS_TRUE ]; then
        return 0
    fi

    # Check if epel repo is already enabled and flag it accordingly
    yum repolist | grep -q "^[!]\?${_EPEL_REPO}/"
    if [ $? -eq 0 ]; then
        _EPEL_REPOS_INSTALLED=$BS_TRUE
        return 0
    fi

    # Download latest 'epel-release' package for the distro version directly
    epel_repo_url="${HTTP_VAL}://dl.fedoraproject.org/pub/epel/epel-release-latest-${DISTRO_MAJOR_VERSION}.noarch.rpm"
    rpm -Uvh --force "$epel_repo_url" || return 1

    _EPEL_REPOS_INSTALLED=$BS_TRUE

    return 0
}

__install_saltstack_copr_zeromq_repository() {
    echoinfo "Installing Zeromq >=4 and PyZMQ>=14 from SaltStack's COPR repository"
    if [ ! -s /etc/yum.repos.d/saltstack-zeromq4.repo ]; then
        if [ "${DISTRO_NAME_L}" = "fedora" ]; then
            __REPOTYPE="${DISTRO_NAME_L}"
        else
            __REPOTYPE="epel"
        fi
        __fetch_url /etc/yum.repos.d/saltstack-zeromq4.repo \
            "${HTTP_VAL}://copr.fedorainfracloud.org/coprs/saltstack/zeromq4/repo/${__REPOTYPE}-${DISTRO_MAJOR_VERSION}/saltstack-zeromq4-${__REPOTYPE}-${DISTRO_MAJOR_VERSION}.repo" || return 1
    fi
    return 0
}

__install_saltstack_rhel_repository() {
    if [ "$ITYPE" = "stable" ]; then
        repo_rev="$STABLE_REV"
    else
        repo_rev="latest"
    fi

    # Avoid using '$releasever' variable for yum.
    # Instead, this should work correctly on all RHEL variants.
    base_url="${HTTP_VAL}://${_REPO_URL}/yum/redhat/${DISTRO_MAJOR_VERSION}/\$basearch/${repo_rev}/"
    gpg_key="SALTSTACK-GPG-KEY.pub"
    repo_file="/etc/yum.repos.d/saltstack.repo"

    if [ ! -s "$repo_file" ]; then
        cat <<_eof > "$repo_file"
[saltstack]
name=SaltStack ${repo_rev} Release Channel for RHEL/CentOS \$releasever
baseurl=${base_url}
skip_if_unavailable=True
gpgcheck=1
gpgkey=${base_url}${gpg_key}
enabled=1
enabled_metadata=1
_eof

        fetch_url="${HTTP_VAL}://${_REPO_URL}/yum/redhat/${DISTRO_MAJOR_VERSION}/${CPU_ARCH_L}/${repo_rev}/"
        __rpm_import_gpg "${fetch_url}${gpg_key}" || return 1
    fi

    return 0
}

__install_saltstack_copr_salt_repository() {
    echoinfo "Adding SaltStack's COPR repository"

    if [ "${DISTRO_NAME_L}" = "fedora" ]; then
        [ "$DISTRO_MAJOR_VERSION" -ge 22 ] && return 0
        __REPOTYPE="${DISTRO_NAME_L}"
    else
        __REPOTYPE="epel"
    fi

    __REPO_FILENAME="saltstack-salt-${__REPOTYPE}-${DISTRO_MAJOR_VERSION}.repo"

    if [ ! -s "/etc/yum.repos.d/${__REPO_FILENAME}" ]; then
        __fetch_url "/etc/yum.repos.d/${__REPO_FILENAME}" \
            "${HTTP_VAL}://copr.fedorainfracloud.org/coprs/saltstack/salt/repo/${__REPOTYPE}-${DISTRO_MAJOR_VERSION}/${__REPO_FILENAME}" || return 1
    fi

    return 0
}

install_centos_stable_deps() {
    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        yum -y update || return 1
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        __install_epel_repository || return 1
        __install_saltstack_rhel_repository || return 1
    fi

    # If -R was passed, we need to configure custom repo url with rsync-ed packages
    # Which is still handled in __install_saltstack_rhel_repository. This call has
    # its own check in case -r was passed without -R.
    if [ "$_CUSTOM_REPO_URL" != "null" ]; then
        __install_saltstack_rhel_repository || return 1
    fi

    # YAML module is used for generating custom master/minion configs
    __PACKAGES="yum-utils chkconfig PyYAML"

    # shellcheck disable=SC2086
    __yum_install_noinput ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __yum_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi


    return 0
}

install_centos_stable() {
    __PACKAGES=""

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-cloud"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    # shellcheck disable=SC2086
    __yum_install_noinput ${__PACKAGES} || return 1

    return 0
}

install_centos_stable_post() {
    SYSTEMD_RELOAD=$BS_FALSE

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            /bin/systemctl is-enabled salt-${fname}.service > /dev/null 2>&1 || (
                /bin/systemctl preset salt-${fname}.service > /dev/null 2>&1 &&
                /bin/systemctl enable salt-${fname}.service > /dev/null 2>&1
            )

            SYSTEMD_RELOAD=$BS_TRUE
        elif [ -f "/etc/init.d/salt-${fname}" ]; then
            /sbin/chkconfig salt-${fname} on
        fi
    done

    if [ "$SYSTEMD_RELOAD" -eq $BS_TRUE ]; then
        /bin/systemctl daemon-reload
    fi

    return 0
}

install_centos_git_deps() {
    install_centos_stable_deps || return 1

    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        __yum_install_noinput ca-certificates || return 1
    fi

    if ! __check_command_exists git; then
        __yum_install_noinput git || return 1
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES="python-crypto python-futures python-msgpack python-zmq python-jinja2 python-requests python-tornado"

    if [ "$DISTRO_MAJOR_VERSION" -ge 7 ]; then
        __PACKAGES="${__PACKAGES} systemd-python"
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-libcloud"
    fi

    if [ "${_INSTALL_PY}" -eq "${BS_TRUE}" ]; then
        # Install Python if "-y" was passed in.
        __install_python || return 1
    fi

    if [ "${_PY_EXE}" != "" ]; then
        # If "-x" is defined, install dependencies with pip based on the Python version given.
        _PIP_PACKAGES="jinja2 msgpack-python pycrypto PyYAML tornado zmq"

        if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
            for SINGLE_PACKAGE in $_PIP_PACKAGES; do
                __REQUIRED_VERSION="$(grep "${SINGLE_PACKAGE}" "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
                if [ "${__REQUIRED_VERSION}" != "" ]; then
                    _PIP_PACKAGES=$(echo "$_PIP_PACKAGES" | sed "s/${SINGLE_PACKAGE}/${__REQUIRED_VERSION}/")
                fi
            done
        fi

        if [ "$_INSTALL_CLOUD" -eq "${BS_TRUE}" ]; then
            _PIP_PACKAGES="${_PIP_PACKAGES} apache-libcloud"
        fi

        __install_pip_pkgs "${_PIP_PACKAGES}" "${_PY_EXE}" || return 1
    else
        # shellcheck disable=SC2086
        __yum_install_noinput ${__PACKAGES} || return 1
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_centos_git() {
    if [ "${_PY_EXE}" != "" ]; then
        _PYEXE=${_PY_EXE}
        echoinfo "Using the following python version: ${_PY_EXE} to install salt"
    else
        _PYEXE='python2'
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        $_PYEXE setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install --prefix=/usr || return 1
    else
        $_PYEXE setup.py ${SETUP_PY_INSTALL_ARGS} install --prefix=/usr || return 1
    fi

    return 0
}

install_centos_git_post() {
    SYSTEMD_RELOAD=$BS_FALSE

    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            if [ ! -f "/usr/lib/systemd/system/salt-${fname}.service" ] || \
                ([ -f "/usr/lib/systemd/system/salt-${fname}.service" ] && [ "$_FORCE_OVERWRITE" -eq $BS_TRUE ]); then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" /usr/lib/systemd/system
            fi

            SYSTEMD_RELOAD=$BS_TRUE
        elif [ ! -f "/etc/init.d/salt-$fname" ] || \
            ([ -f "/etc/init.d/salt-$fname" ] && [ "$_FORCE_OVERWRITE" -eq $BS_TRUE ]); then
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}" /etc/init.d
            chmod +x /etc/init.d/salt-${fname}
        fi
    done

    if [ "$SYSTEMD_RELOAD" -eq $BS_TRUE ]; then
        /bin/systemctl daemon-reload
    fi

    install_centos_stable_post || return 1

    return 0
}

install_centos_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /sbin/initctl ] && [ -f /etc/init/salt-${fname}.conf ]; then
            # We have upstart support and upstart knows about our service
            /sbin/initctl status salt-$fname > /dev/null 2>&1
            if [ $? -ne 0 ]; then
                # Everything is in place and upstart gave us an error code? Fail!
                return 1
            fi

            # upstart knows about this service.
            # Let's try to stop it, and then start it
            /sbin/initctl stop salt-$fname > /dev/null 2>&1
            /sbin/initctl start salt-$fname > /dev/null 2>&1
            # Restart service
            if [ $? -ne 0 ]; then
                # Failed the restart?!
                return 1
            fi
        elif [ -f /etc/init.d/salt-$fname ]; then
            # Disable stdin to fix shell session hang on killing tee pipe
            service salt-$fname stop < /dev/null > /dev/null 2>&1
            service salt-$fname start < /dev/null
        elif [ -f /usr/bin/systemctl ]; then
            # CentOS 7 uses systemd
            /usr/bin/systemctl stop salt-$fname > /dev/null 2>&1
            /usr/bin/systemctl start salt-$fname.service
        fi
    done
}

install_centos_testing_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_centos_testing() {
    install_centos_stable || return 1
    return 0
}

install_centos_testing_post() {
    install_centos_stable_post || return 1
    return 0
}

install_centos_check_services() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /sbin/initctl ] && [ -f /etc/init/salt-${fname}.conf ]; then
            __check_services_upstart salt-$fname || return 1
        elif [ -f /etc/init.d/salt-$fname ]; then
            __check_services_sysvinit salt-$fname || return 1
        elif [ -f /usr/bin/systemctl ]; then
            __check_services_systemd salt-$fname || return 1
        fi
    done

    return 0
}
#
#   Ended CentOS Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   RedHat Install Functions
#
install_red_hat_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_red_hat_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_red_hat_enterprise_linux_stable_deps() {
    install_red_hat_linux_stable_deps || return 1
    return 0
}

install_red_hat_enterprise_linux_git_deps() {
    install_red_hat_linux_git_deps || return 1
    return 0
}

install_red_hat_enterprise_server_stable_deps() {
    install_red_hat_linux_stable_deps || return 1
    return 0
}

install_red_hat_enterprise_server_git_deps() {
    install_red_hat_linux_git_deps || return 1
    return 0
}

install_red_hat_enterprise_workstation_stable_deps() {
    install_red_hat_linux_stable_deps || return 1
    return 0
}

install_red_hat_enterprise_workstation_git_deps() {
    install_red_hat_linux_git_deps || return 1
    return 0
}

install_red_hat_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_red_hat_linux_git() {
    install_centos_git || return 1
    return 0
}

install_red_hat_enterprise_linux_stable() {
    install_red_hat_linux_stable || return 1
    return 0
}

install_red_hat_enterprise_linux_git() {
    install_red_hat_linux_git || return 1
    return 0
}

install_red_hat_enterprise_server_stable() {
    install_red_hat_linux_stable || return 1
    return 0
}

install_red_hat_enterprise_server_git() {
    install_red_hat_linux_git || return 1
    return 0
}

install_red_hat_enterprise_workstation_stable() {
    install_red_hat_linux_stable || return 1
    return 0
}

install_red_hat_enterprise_workstation_git() {
    install_red_hat_linux_git || return 1
    return 0
}

install_red_hat_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_red_hat_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_red_hat_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_red_hat_enterprise_linux_stable_post() {
    install_red_hat_linux_stable_post || return 1
    return 0
}

install_red_hat_enterprise_linux_restart_daemons() {
    install_red_hat_linux_restart_daemons || return 1
    return 0
}

install_red_hat_enterprise_linux_git_post() {
    install_red_hat_linux_git_post || return 1
    return 0
}

install_red_hat_enterprise_server_stable_post() {
    install_red_hat_linux_stable_post || return 1
    return 0
}

install_red_hat_enterprise_server_restart_daemons() {
    install_red_hat_linux_restart_daemons || return 1
    return 0
}

install_red_hat_enterprise_server_git_post() {
    install_red_hat_linux_git_post || return 1
    return 0
}

install_red_hat_enterprise_workstation_stable_post() {
    install_red_hat_linux_stable_post || return 1
    return 0
}

install_red_hat_enterprise_workstation_restart_daemons() {
    install_red_hat_linux_restart_daemons || return 1
    return 0
}

install_red_hat_enterprise_workstation_git_post() {
    install_red_hat_linux_git_post || return 1
    return 0
}

install_red_hat_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_red_hat_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_red_hat_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_red_hat_enterprise_server_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_red_hat_enterprise_server_testing() {
    install_centos_testing || return 1
    return 0
}

install_red_hat_enterprise_server_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_red_hat_enterprise_workstation_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_red_hat_enterprise_workstation_testing() {
    install_centos_testing || return 1
    return 0
}

install_red_hat_enterprise_workstation_testing_post() {
    install_centos_testing_post || return 1
    return 0
}
#
#   Ended RedHat Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Oracle Linux Install Functions
#
install_oracle_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_oracle_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_oracle_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_oracle_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_oracle_linux_git() {
    install_centos_git || return 1
    return 0
}

install_oracle_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_oracle_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_oracle_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_oracle_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_oracle_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_oracle_linux_check_services() {
    install_centos_check_services || return 1
    return 0
}
#
#   Ended Oracle Linux Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Scientific Linux Install Functions
#
install_scientific_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_scientific_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_scientific_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_scientific_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_scientific_linux_git() {
    install_centos_git || return 1
    return 0
}

install_scientific_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_scientific_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_scientific_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_scientific_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_scientific_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_scientific_linux_check_services() {
    install_centos_check_services || return 1
    return 0
}
#
#   Ended Scientific Linux Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   CloudLinux Install Functions
#
install_cloud_linux_stable_deps() {
    install_centos_stable_deps || return 1
    return 0
}

install_cloud_linux_git_deps() {
    install_centos_git_deps || return 1
    return 0
}

install_cloud_linux_testing_deps() {
    install_centos_testing_deps || return 1
    return 0
}

install_cloud_linux_stable() {
    install_centos_stable || return 1
    return 0
}

install_cloud_linux_git() {
    install_centos_git || return 1
    return 0
}

install_cloud_linux_testing() {
    install_centos_testing || return 1
    return 0
}

install_cloud_linux_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_cloud_linux_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_cloud_linux_testing_post() {
    install_centos_testing_post || return 1
    return 0
}

install_cloud_linux_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_cloud_linux_check_services() {
    install_centos_check_services || return 1
    return 0
}
#
#   End of CloudLinux Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Alpine Linux Install Functions
#
install_alpine_linux_stable_deps() {
    if ! grep -q '^[^#].\+alpine/.\+/community' /etc/apk/repositories; then
        # Add community repository entry based on the "main" repo URL
        __REPO=$(grep '^[^#].\+alpine/.\+/main\>' /etc/apk/repositories)
        echo "${__REPO}" | sed -e 's/main/community/' >> /etc/apk/repositories
    fi

    apk update

    # Get latest root CA certs
    apk -U add ca-certificates

    if ! __check_command_exists openssl; then
        # Install OpenSSL to be able to pull from https:// URLs
        apk -U add openssl
    fi
}

install_alpine_linux_git_deps() {
    install_alpine_linux_stable_deps || return 1

    apk -U add python2 py-virtualenv py2-crypto py2-setuptools \
        py2-jinja2 py2-yaml py2-markupsafe py2-msgpack py2-psutil \
        py2-zmq zeromq py2-requests || return 1

    if ! __check_command_exists git; then
        apk -U add git  || return 1
    fi

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            apk -U add py2-tornado || return 1
        fi
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi
}

install_alpine_linux_stable() {
    __PACKAGES="salt"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-cloud"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    # shellcheck disable=SC2086
    apk -U add ${__PACKAGES} || return 1
    return 0
}

install_alpine_linux_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python2 setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install || return 1
    else
        python2 setup.py ${SETUP_PY_INSTALL_ARGS} install || return 1
    fi
}

install_alpine_linux_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /sbin/rc-update ]; then
            script_url="${_SALTSTACK_REPO_URL%.git}/raw/develop/pkg/alpine/salt-$fname"
            [ -f "/etc/init.d/salt-$fname" ] || __fetch_url "/etc/init.d/salt-$fname" "$script_url"

            if [ $? -eq 0 ]; then
                chmod +x "/etc/init.d/salt-$fname"
            else
                echoerror "Failed to get OpenRC init script for $OS_NAME from $script_url."
                return 1
            fi

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /sbin/rc-update add "salt-$fname" > /dev/null 2>&1 || return 1
        fi
    done
}

install_alpine_linux_restart_daemons() {
    [ "${_START_DAEMONS}" -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue

        # Disable stdin to fix shell session hang on killing tee pipe
        /sbin/rc-service salt-$fname stop < /dev/null > /dev/null 2>&1
        /sbin/rc-service salt-$fname start < /dev/null || return 1
    done
}

install_alpine_linux_check_services() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue

        __check_services_alpine salt-$fname || return 1
    done

    return 0
}

daemons_running_alpine_linux() {
    [ "${_START_DAEMONS}" -eq $BS_FALSE ] && return

    FAILED_DAEMONS=0
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue

        # shellcheck disable=SC2009
        if [ "$(ps wwwaux | grep -v grep | grep salt-$fname)" = "" ]; then
            echoerror "salt-$fname was not found running"
            FAILED_DAEMONS=$((FAILED_DAEMONS + 1))
        fi
    done

    return $FAILED_DAEMONS
}

#
#   Ended Alpine Linux Install Functions
#
#######################################################################################################################


#######################################################################################################################
#
#   Amazon Linux AMI Install Functions
#

install_amazon_linux_ami_deps() {
    # Shim to figure out if we're using old (rhel) or new (aws) rpms.
    _USEAWS=$BS_FALSE
    pkg_append="python"

    repo_rev="$(echo "${STABLE_REV}"  | sed 's|.*\/||g')"

    if echo "$repo_rev" | egrep -q '^(latest|2016\.11)$' || \
            [ "$(echo "$repo_rev" | cut -c1-4)" -gt 2016 ]; then
       _USEAWS=$BS_TRUE
       pkg_append="python27"
    fi

    # We need to install yum-utils before doing anything else when installing on
    # Amazon Linux ECS-optimized images. See issue #974.
    __yum_install_noinput yum-utils

    # Do upgrade early
    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        yum -y update || return 1
    fi

    if [ $_DISABLE_REPOS -eq $BS_FALSE ] || [ "$_CUSTOM_REPO_URL" != "null" ]; then
        __REPO_FILENAME="saltstack-repo.repo"

        # Set a few vars to make life easier.
        if [ $_USEAWS -eq $BS_TRUE ]; then
           base_url="$HTTP_VAL://${_REPO_URL}/yum/amazon/latest/\$basearch/$repo_rev/"
           gpg_key="${base_url}SALTSTACK-GPG-KEY.pub"
           repo_name="SaltStack repo for Amazon Linux"
        else
           base_url="$HTTP_VAL://${_REPO_URL}/yum/redhat/6/\$basearch/$repo_rev/"
           gpg_key="${base_url}SALTSTACK-GPG-KEY.pub"
           repo_name="SaltStack repo for RHEL/CentOS 6"
        fi

        # This should prob be refactored to use __install_saltstack_rhel_repository()
        # With args passed in to do the right thing.  Reformatted to be more like the
        # amazon linux yum file.
        if [ ! -s "/etc/yum.repos.d/${__REPO_FILENAME}" ]; then
          cat <<_eof > "/etc/yum.repos.d/${__REPO_FILENAME}"
[saltstack-repo]
name=$repo_name
failovermethod=priority
priority=10
gpgcheck=1
gpgkey=$gpg_key
baseurl=$base_url
_eof
        fi

    fi

    # Package python-ordereddict-1.1-2.el6.noarch is obsoleted by python26-2.6.9-2.88.amzn1.x86_64
    # which is already installed
    __PACKAGES="${pkg_append}-PyYAML ${pkg_append}-crypto ${pkg_append}-msgpack ${pkg_append}-zmq ${pkg_append}-jinja2 ${pkg_append}-requests"

    # shellcheck disable=SC2086
    __yum_install_noinput ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __yum_install_noinput ${_EXTRA_PACKAGES} || return 1
    fi
}

install_amazon_linux_ami_git_deps() {
    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        yum -y install ca-certificates || return 1
    fi

    PIP_EXE='pip'
    if __check_command_exists python2.7; then
        if ! __check_command_exists pip2.7; then
            /usr/bin/easy_install-2.7 pip || return 1
        fi
        PIP_EXE='/usr/local/bin/pip2.7'
        _PY_EXE='python2.7'
    fi

    install_amazon_linux_ami_deps || return 1

    if ! __check_command_exists git; then
        __yum_install_noinput git || return 1
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES=""
    __PIP_PACKAGES=""

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install apache-libcloud"
        __PACKAGES="${__PACKAGES} python-pip"
        __PIP_PACKAGES="${__PIP_PACKAGES} apache-libcloud>=$_LIBCLOUD_MIN_VERSION"
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __PACKAGES="${__PACKAGES} ${pkg_append}-tornado"
        fi
    fi

    if [ "${__PACKAGES}" != "" ]; then
        # shellcheck disable=SC2086
        __yum_install_noinput ${__PACKAGES} || return 1
    fi

    if [ "${__PIP_PACKAGES}" != "" ]; then
        # shellcheck disable=SC2086
        ${PIP_EXE} install ${__PIP_PACKAGES} || return 1
    fi

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_amazon_linux_ami_stable() {
    install_centos_stable || return 1
    return 0
}

install_amazon_linux_ami_stable_post() {
    install_centos_stable_post || return 1
    return 0
}

install_amazon_linux_ami_restart_daemons() {
    install_centos_restart_daemons || return 1
    return 0
}

install_amazon_linux_ami_git() {
    install_centos_git || return 1
    return 0
}

install_amazon_linux_ami_git_post() {
    install_centos_git_post || return 1
    return 0
}

install_amazon_linux_ami_testing() {
    install_centos_testing || return 1
    return 0
}

install_amazon_linux_ami_testing_post() {
    install_centos_testing_post || return 1
    return 0
}
#
#   Ended Amazon Linux AMI Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Arch Install Functions
#
install_arch_linux_stable_deps() {
    if [ ! -f /etc/pacman.d/gnupg ]; then
        pacman-key --init && pacman-key --populate archlinux || return 1
    fi

    # Pacman does not resolve dependencies on outdated versions
    # They always need to be updated
    pacman -Syy --noconfirm

    pacman -S --noconfirm --needed archlinux-keyring || return 1

    pacman -Su --noconfirm --needed pacman || return 1

    if __check_command_exists pacman-db-upgrade; then
        pacman-db-upgrade || return 1
    fi

    # YAML module is used for generating custom master/minion configs
    pacman -Su --noconfirm --needed python2-yaml

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        pacman -Su --noconfirm --needed python2-apache-libcloud || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        pacman -Su --noconfirm --needed ${_EXTRA_PACKAGES} || return 1
    fi
}

install_arch_linux_git_deps() {
    install_arch_linux_stable_deps

    # Don't fail if un-installing python2-distribute threw an error
    if ! __check_command_exists git; then
        pacman -Sy --noconfirm --needed git  || return 1
    fi
    pacman -R --noconfirm python2-distribute
    pacman -Su --noconfirm --needed python2-crypto python2-setuptools python2-jinja \
        python2-markupsafe python2-msgpack python2-psutil \
        python2-pyzmq zeromq python2-requests python2-systemd || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            pacman -Su --noconfirm --needed python2-tornado
        fi
    fi


    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_arch_linux_stable() {
    # Pacman does not resolve dependencies on outdated versions
    # They always need to be updated
    pacman -Syy --noconfirm

    pacman -Su --noconfirm --needed pacman || return 1
    # See https://mailman.archlinux.org/pipermail/arch-dev-public/2013-June/025043.html
    # to know why we're ignoring below.
    pacman -Syu --noconfirm --ignore filesystem,bash || return 1
    pacman -S --noconfirm --needed bash || return 1
    pacman -Su --noconfirm || return 1
    # We can now resume regular salt update
    pacman -Syu --noconfirm salt || return 1
    return 0
}

install_arch_linux_git() {
    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/salt/syspaths.py" ]; then
        python2 setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install || return 1
    else
        python2 setup.py ${SETUP_PY_INSTALL_ARGS} install || return 1
    fi
    return 0
}

install_arch_linux_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Since Arch's pacman renames configuration files
        if [ "$_TEMP_CONFIG_DIR" != "null" ] && [ -f "$_SALT_ETC_DIR/$fname.pacorig" ]; then
            # Since a configuration directory was provided, it also means that any
            # configuration file copied was renamed by Arch, see:
            #   https://wiki.archlinux.org/index.php/Pacnew_and_Pacsave_Files#.pacorig
            __copyfile "$_SALT_ETC_DIR/$fname.pacorig" "$_SALT_ETC_DIR/$fname" $BS_TRUE
        fi

        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        if [ -f /usr/bin/systemctl ]; then
            # Using systemd
            /usr/bin/systemctl is-enabled salt-$fname.service > /dev/null 2>&1 || (
                /usr/bin/systemctl preset salt-$fname.service > /dev/null 2>&1 &&
                /usr/bin/systemctl enable salt-$fname.service > /dev/null 2>&1
            )
            sleep 0.1
            /usr/bin/systemctl daemon-reload
            continue
        fi

        # XXX: How do we enable old Arch init.d scripts?
    done
}

install_arch_linux_git_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /usr/bin/systemctl ]; then
            __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"

            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            /usr/bin/systemctl is-enabled salt-${fname}.service > /dev/null 2>&1 || (
                /usr/bin/systemctl preset salt-${fname}.service > /dev/null 2>&1 &&
                /usr/bin/systemctl enable salt-${fname}.service > /dev/null 2>&1
            )
            sleep 0.1
            /usr/bin/systemctl daemon-reload
            continue
        fi

        # SysV init!?
        __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-$fname" "/etc/rc.d/init.d/salt-$fname"
        chmod +x /etc/rc.d/init.d/salt-$fname
    done
}

install_arch_linux_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /usr/bin/systemctl ]; then
            /usr/bin/systemctl stop salt-$fname.service > /dev/null 2>&1
            /usr/bin/systemctl start salt-$fname.service
            continue
        fi

        /etc/rc.d/salt-$fname stop > /dev/null 2>&1
        /etc/rc.d/salt-$fname start
    done
}

install_arch_check_services() {
    if [ ! -f /usr/bin/systemctl ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __check_services_systemd salt-$fname || return 1
    done

    return 0
}
#
#   Ended Arch Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   FreeBSD Install Functions
#

__freebsd_get_packagesite() {
    if [ "$CPU_ARCH_L" = "amd64" ]; then
        BSD_ARCH="x86:64"
    elif [ "$CPU_ARCH_L" = "x86_64" ]; then
        BSD_ARCH="x86:64"
    elif [ "$CPU_ARCH_L" = "i386" ]; then
        BSD_ARCH="x86:32"
    elif [ "$CPU_ARCH_L" = "i686" ]; then
        BSD_ARCH="x86:32"
    fi

    # Since the variable might not be set, don't, momentarily treat it as a
    # failure
    set +o nounset

    # ABI is a std format for identifying release / architecture combos
    ABI="freebsd:${DISTRO_MAJOR_VERSION}:${BSD_ARCH}"
    _PACKAGESITE="http://pkg.freebsd.org/${ABI}/latest"
    # Awkwardly, we want the `${ABI}` to be in conf file without escaping
    PKGCONFURL="pkg+http://pkg.freebsd.org/\${ABI}/latest"
    SALTPKGCONFURL="http://repo.saltstack.com/freebsd/\${ABI}/"

    # Treat unset variables as errors once more
    set -o nounset
}

# Using a separate conf step to head for idempotent install...
__configure_freebsd_pkg_details() {
    ## pkg.conf is deprecated.
    ## We use conf files in /usr/local or /etc instead
    mkdir -p /usr/local/etc/pkg/repos/
    mkdir -p /etc/pkg/

    ## Use new JSON-like format for pkg repo configs
    ## check if /etc/pkg/FreeBSD.conf is already in place
    if [ ! -f /etc/pkg/FreeBSD.conf ]; then
      conf_file=/usr/local/etc/pkg/repos/freebsd.conf
      {
          echo "FreeBSD:{"
          echo "    url: \"${PKGCONFURL}\","
          echo "    mirror_type: \"srv\","
          echo "    signature_type: \"fingerprints\","
          echo "    fingerprints: \"/usr/share/keys/pkg\","
          echo "    enabled: true"
          echo "}"
      } > $conf_file
      __copyfile $conf_file /etc/pkg/FreeBSD.conf
    fi
    FROM_FREEBSD="-r FreeBSD"

    ## add saltstack freebsd repo
    salt_conf_file=/usr/local/etc/pkg/repos/saltstack.conf
    {
        echo "SaltStack:{"
        echo "    url: \"${SALTPKGCONFURL}\","
        echo "    mirror_type: \"http\","
        echo "    enabled: true"
        echo "    priority: 10"
        echo "}"
    } > $salt_conf_file
    FROM_SALTSTACK="-r SaltStack"

    ## ensure future ports builds use pkgng
    echo "WITH_PKGNG=   yes" >> /etc/make.conf

    /usr/local/sbin/pkg update -f || return 1
}

install_freebsd_9_stable_deps() {
    _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/usr/local/etc/salt}
    _PKI_DIR=${_SALT_ETC_DIR}/pki

    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        #make variables available even if pkg already installed
        __freebsd_get_packagesite

        if [ ! -x /usr/local/sbin/pkg ]; then

            # install new `pkg` code from its own tarball.
            fetch "${_PACKAGESITE}/Latest/pkg.txz" || return 1
            tar xf ./pkg.txz -s ",/.*/,,g" "*/pkg-static" || return 1
            ./pkg-static add ./pkg.txz || return 1
            /usr/local/sbin/pkg2ng || return 1
        fi

        # Configure the pkg repository using new approach
        __configure_freebsd_pkg_details || return 1
    fi

    # Now install swig
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y swig || return 1

    # YAML module is used for generating custom master/minion configs
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y py27-yaml || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        /usr/local/sbin/pkg install ${FROM_FREEBSD} -y ${_EXTRA_PACKAGES} || return 1
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        pkg upgrade -y || return 1
    fi

    return 0
}

install_freebsd_10_stable_deps() {
    install_freebsd_9_stable_deps
}

install_freebsd_11_stable_deps() {
    install_freebsd_9_stable_deps
}

install_freebsd_git_deps() {
    install_freebsd_9_stable_deps || return 1

    # shellcheck disable=SC2086
    SALT_DEPENDENCIES=$(/usr/local/sbin/pkg search ${FROM_FREEBSD} -R -d sysutils/py-salt | grep -i origin | sed -e 's/^[[:space:]]*//' | tail -n +2 | awk -F\" '{print $2}' | tr '\n' ' ')
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y ${SALT_DEPENDENCIES} || return 1

    if ! __check_command_exists git; then
        /usr/local/sbin/pkg install -y git || return 1
    fi

    /usr/local/sbin/pkg install -y www/py-requests || return 1

    __git_clone_and_checkout || return 1

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
             /usr/local/sbin/pkg install -y www/py-tornado || return 1
        fi
    fi

    echodebug "Adapting paths to FreeBSD"
    # The list of files was taken from Salt's BSD port Makefile
    for file in doc/man/salt-key.1 doc/man/salt-cp.1 doc/man/salt-minion.1 \
                doc/man/salt-syndic.1 doc/man/salt-master.1 doc/man/salt-run.1 \
                doc/man/salt.7 doc/man/salt.1 doc/man/salt-call.1; do
        [ ! -f $file ] && continue
        echodebug "Patching ${file}"
        sed -in -e "s|/etc/salt|${_SALT_ETC_DIR}|" \
                -e "s|/srv/salt|${_SALT_ETC_DIR}/states|" \
                -e "s|/srv/pillar|${_SALT_ETC_DIR}/pillar|" ${file}
    done
    if [ ! -f salt/syspaths.py ]; then
        # We still can't provide the system paths, salt 0.16.x
        # Let's patch salt's source and adapt paths to what's expected on FreeBSD
        echodebug "Replacing occurrences of '/etc/salt' with \'${_SALT_ETC_DIR}\'"
        # The list of files was taken from Salt's BSD port Makefile
        for file in conf/minion conf/master salt/config.py salt/client.py \
                    salt/modules/mysql.py salt/utils/parsers.py salt/modules/tls.py \
                    salt/modules/postgres.py salt/utils/migrations.py; do
            [ ! -f $file ] && continue
            echodebug "Patching ${file}"
            sed -in -e "s|/etc/salt|${_SALT_ETC_DIR}|" \
                    -e "s|/srv/salt|${_SALT_ETC_DIR}/states|" \
                    -e "s|/srv/pillar|${_SALT_ETC_DIR}/pillar|" ${file}
        done
    fi
    echodebug "Finished patching"

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"

    fi

    return 0
}

install_freebsd_9_stable() {
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_SALTSTACK} -y sysutils/py-salt || return 1
    return 0
}

install_freebsd_10_stable() {
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y sysutils/py-salt || return 1
    return 0
}

install_freebsd_11_stable() {
#
# installing latest version of salt from FreeBSD CURRENT ports repo
#
    # shellcheck disable=SC2086
    /usr/local/sbin/pkg install ${FROM_FREEBSD} -y sysutils/py-salt || return 1

    return 0
}

install_freebsd_git() {

    # /usr/local/bin/python2 in FreeBSD is a symlink to /usr/local/bin/python2.7
    __PYTHON_PATH=$(readlink -f "$(which python2)")
    __ESCAPED_PYTHON_PATH=$(echo "${__PYTHON_PATH}" | sed 's/\//\\\//g')

    # Install from git
    if [ ! -f salt/syspaths.py ]; then
        # We still can't provide the system paths, salt 0.16.x
        ${__PYTHON_PATH} setup.py ${SETUP_PY_INSTALL_ARGS} install || return 1
    else
        ${__PYTHON_PATH} setup.py \
            --salt-root-dir=/ \
            --salt-config-dir="${_SALT_ETC_DIR}" \
            --salt-cache-dir="${_SALT_CACHE_DIR}" \
            --salt-sock-dir=/var/run/salt \
            --salt-srv-root-dir="${_SALT_ETC_DIR}" \
            --salt-base-file-roots-dir="${_SALT_ETC_DIR}/states" \
            --salt-base-pillar-roots-dir="${_SALT_ETC_DIR}/pillar" \
            --salt-base-master-roots-dir="${_SALT_ETC_DIR}/salt-master" \
            --salt-logs-dir=/var/log/salt \
            --salt-pidfile-dir=/var/run \
            ${SETUP_PY_INSTALL_ARGS} install \
            || return 1
    fi

    for script in salt_api salt_master salt_minion salt_proxy salt_syndic; do
        __fetch_url "/usr/local/etc/rc.d/${script}" "https://raw.githubusercontent.com/freebsd/freebsd-ports/master/sysutils/py-salt/files/${script}.in" || return 1
        sed -i '' 's/%%PREFIX%%/\/usr\/local/g' /usr/local/etc/rc.d/${script}
        sed -i '' "s/%%PYTHON_CMD%%/${__ESCAPED_PYTHON_PATH}/g" /usr/local/etc/rc.d/${script}
        chmod +x /usr/local/etc/rc.d/${script} || return 1
    done

    # And we're good to go
    return 0
}

install_freebsd_9_stable_post() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        enable_string="salt_${fname}_enable=\"YES\""
        grep "$enable_string" /etc/rc.conf >/dev/null 2>&1
        [ $? -eq 1 ] && echo "$enable_string" >> /etc/rc.conf

        if [ $fname = "minion" ] ; then
            grep "salt_minion_paths" /etc/rc.conf >/dev/null 2>&1
            [ $? -eq 1 ] && echo "salt_minion_paths=\"/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin\"" >> /etc/rc.conf
        fi
    done
}

install_freebsd_10_stable_post() {
    install_freebsd_9_stable_post
}

install_freebsd_11_stable_post() {
    install_freebsd_9_stable_post
}

install_freebsd_git_post() {
    if [ -f $salt_conf_file ]; then
        rm -f $salt_conf_file
    fi
    install_freebsd_9_stable_post || return 1
    return 0
}

install_freebsd_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        service salt_$fname stop > /dev/null 2>&1
        service salt_$fname start
    done
}
#
#   Ended FreeBSD Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   OpenBSD Install Functions
#

__choose_openbsd_mirror() {
    OPENBSD_REPO=''
    MINTIME=''
    MIRROR_LIST=$(ftp -w 15 -Vao - 'https://ftp.openbsd.org/cgi-bin/ftplist.cgi?dbversion=1' | awk '/^http/ {print $1}')

    for MIRROR in $MIRROR_LIST; do
        MIRROR_HOST=$(echo "$MIRROR" | sed -e 's|.*//||' -e 's|+*/.*$||')
        TIME=$(ping -c 1 -w 1 -q "$MIRROR_HOST" | awk -F/ '/round-trip/ { print $5 }')
        [ -z "$TIME" ] && continue

        echodebug "ping time for $MIRROR_HOST is $TIME"
        if [ -z "$MINTIME" ]; then
            FASTER_MIRROR=1
        else
            FASTER_MIRROR=$(echo "$TIME < $MINTIME" | bc)
        fi
        if [ "$FASTER_MIRROR" -eq 1 ]; then
            MINTIME=$TIME
            OPENBSD_REPO="$MIRROR"
        fi
    done
}

install_openbsd_deps() {
    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        __choose_openbsd_mirror || return 1
        echoinfo "setting package repository to $OPENBSD_REPO with ping time of $MINTIME"
        [ -n "$OPENBSD_REPO" ] || return 1
        echo "${OPENBSD_REPO}" >>/etc/installurl || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        pkg_add -I -v ${_EXTRA_PACKAGES} || return 1
    fi
    return 0
}

install_openbsd_git_deps() {
    install_openbsd_deps || return 1
    pkg_add -I -v git || return 1
    __git_clone_and_checkout || return 1
    #
    # Let's trigger config_salt()
    #
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi
    return 0
}

install_openbsd_git() {
    #
    # Install from git
    #
    if [ ! -f salt/syspaths.py ]; then
        # We still can't provide the system paths, salt 0.16.x
        /usr/local/bin/python2.7 setup.py ${SETUP_PY_INSTALL_ARGS} install || return 1
    fi
    return 0
}

install_openbsd_stable() {
    pkg_add -r -I -v salt || return 1
    return 0
}

install_openbsd_post() {
    for fname in api master minion syndic; do
        [ $fname = "api" ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        rcctl enable salt_$fname
    done

    return 0
}

install_openbsd_check_services() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && continue

        if [ -f /etc/rc.d/salt_${fname} ]; then
            __check_services_openbsd salt_${fname} || return 1
        fi
    done

    return 0
}

install_openbsd_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        rcctl restart salt_${fname}
    done

    return 0
}

#
#   Ended OpenBSD Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   SmartOS Install Functions
#
install_smartos_deps() {
    pkgin -y install zeromq py27-crypto py27-msgpack py27-yaml py27-jinja2 py27-zmq py27-requests || return 1

    # Set _SALT_ETC_DIR to SmartOS default if they didn't specify
    _SALT_ETC_DIR=${BS_SALT_ETC_DIR:-/opt/local/etc/salt}
    # We also need to redefine the PKI directory
    _PKI_DIR=${_SALT_ETC_DIR}/pki

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        # Let's set the configuration directory to /tmp
        _TEMP_CONFIG_DIR="/tmp"
        CONFIG_SALT_FUNC="config_salt"

        # Let's download, since they were not provided, the default configuration files
        if [ ! -f "$_SALT_ETC_DIR/minion" ] && [ ! -f "$_TEMP_CONFIG_DIR/minion" ]; then
            # shellcheck disable=SC2086
            curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/minion" -L \
                https://raw.githubusercontent.com/saltstack/salt/develop/conf/minion || return 1
        fi
        if [ ! -f "$_SALT_ETC_DIR/master" ] && [ ! -f $_TEMP_CONFIG_DIR/master ]; then
            # shellcheck disable=SC2086
            curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/master" -L \
                https://raw.githubusercontent.com/saltstack/salt/develop/conf/master || return 1
        fi
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE  ]; then
        pkgin -y install py27-apache-libcloud || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        pkgin -y install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_smartos_git_deps() {
    install_smartos_deps || return 1

    if ! __check_command_exists git; then
        pkgin -y install git || return 1
    fi

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # Install whichever tornado is in the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_TORNADO}'"

        # Install whichever futures is in the requirements file
        __REQUIRED_FUTURES="$(grep futures "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        __check_pip_allowed "You need to allow pip based installations (-P) in order to install the python package '${__REQUIRED_FUTURES}'"

        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            if ! __check_command_exists pip; then
                pkgin -y install py27-pip
            fi
            pip install -U "${__REQUIRED_TORNADO}"
        fi

        if [ "${__REQUIRED_FUTURES}" != "" ]; then
            if ! __check_command_exists pip; then
                pkgin -y install py27-pip
            fi
            pip install -U "${__REQUIRED_FUTURES}"
        fi
    fi

    __git_clone_and_checkout || return 1
    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_smartos_stable() {
    pkgin -y install salt || return 1
    return 0
}

install_smartos_git() {
    # Use setuptools in order to also install dependencies
    # lets force our config path on the setup for now, since salt/syspaths.py only  got fixed in 2015.5.0
    USE_SETUPTOOLS=1 /opt/local/bin/python setup.py --salt-config-dir="$_SALT_ETC_DIR" --salt-cache-dir="${_SALT_CACHE_DIR}" ${SETUP_PY_INSTALL_ARGS} install || return 1
    return 0
}

install_smartos_post() {
    smf_dir="/opt/custom/smf"

    # Install manifest files if needed.
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        svcs network/salt-$fname > /dev/null 2>&1
        if [ $? -eq 1 ]; then
            if [ ! -f "$_TEMP_CONFIG_DIR/salt-$fname.xml" ]; then
                # shellcheck disable=SC2086
                curl $_CURL_ARGS -s -o "$_TEMP_CONFIG_DIR/salt-$fname.xml" -L \
                    "https://raw.githubusercontent.com/saltstack/salt/develop/pkg/smartos/salt-$fname.xml"
            fi
            svccfg import "$_TEMP_CONFIG_DIR/salt-$fname.xml"
            if [ "${VIRTUAL_TYPE}" = "global" ]; then
                if [ ! -d "$smf_dir" ]; then
                    mkdir -p "$smf_dir" || return 1
                fi
                if [ ! -f "$smf_dir/salt-$fname.xml" ]; then
                    __copyfile "$_TEMP_CONFIG_DIR/salt-$fname.xml" "$smf_dir/" || return 1
                fi
            fi
        fi
    done

    return 0
}

install_smartos_git_post() {
    smf_dir="/opt/custom/smf"

    # Install manifest files if needed.
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        svcs "network/salt-$fname" > /dev/null 2>&1
        if [ $? -eq 1 ]; then
            svccfg import "${_SALT_GIT_CHECKOUT_DIR}/pkg/smartos/salt-$fname.xml"
            if [ "${VIRTUAL_TYPE}" = "global" ]; then
                if [ ! -d $smf_dir ]; then
                    mkdir -p "$smf_dir"
                fi
                if [ ! -f "$smf_dir/salt-$fname.xml" ]; then
                    __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/smartos/salt-$fname.xml" "$smf_dir/"
                fi
            fi
        fi
    done

    return 0
}

install_smartos_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # Stop if running && Start service
        svcadm disable salt-$fname > /dev/null 2>&1
        svcadm enable salt-$fname
    done

    return 0
}
#
#   Ended SmartOS Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#    openSUSE Install Functions.
#
__ZYPPER_REQUIRES_REPLACE_FILES=-1

__set_suse_pkg_repo() {

    # Set distro repo variable
    if [ "${DISTRO_MAJOR_VERSION}" -gt 2015 ]; then
        DISTRO_REPO="openSUSE_Tumbleweed"
    elif [ "${DISTRO_MAJOR_VERSION}" -ge 42 ]; then
        DISTRO_REPO="openSUSE_Leap_${DISTRO_MAJOR_VERSION}.${DISTRO_MINOR_VERSION}"
    elif [ "${DISTRO_MAJOR_VERSION}" -lt 42 ]; then
        DISTRO_REPO="SLE_${DISTRO_MAJOR_VERSION}_SP${SUSE_PATCHLEVEL}"
    fi

    if [ "$_DOWNSTREAM_PKG_REPO" -eq $BS_TRUE ]; then
        suse_pkg_url_base="https://download.opensuse.org/repositories/systemsmanagement:/saltstack"
        suse_pkg_url_path="${DISTRO_REPO}/systemsmanagement:saltstack.repo"
    else
        suse_pkg_url_base="${HTTP_VAL}://repo.saltstack.com/opensuse"
        suse_pkg_url_path="${DISTRO_REPO}/systemsmanagement:saltstack:products.repo"
    fi
    SUSE_PKG_URL="$suse_pkg_url_base/$suse_pkg_url_path"
}

__check_and_refresh_suse_pkg_repo() {
    # Check to see if systemsmanagement_saltstack exists
    __zypper repos | grep -q systemsmanagement_saltstack

    if [ $? -eq 1 ]; then
        # zypper does not yet know anything about systemsmanagement_saltstack
        __zypper addrepo --refresh "${SUSE_PKG_URL}" || return 1
    fi
}

__version_lte() {
    if ! __check_command_exists python; then
        zypper zypper --non-interactive install --replacefiles --auto-agree-with-licenses python || \
             zypper zypper --non-interactive install --auto-agree-with-licenses python || return 1
    fi

    if [ "$(python -c 'import sys; V1=tuple([int(i) for i in sys.argv[1].split(".")]); V2=tuple([int(i) for i in sys.argv[2].split(".")]); print V1<=V2' "$1" "$2")" = "True" ]; then
        __ZYPPER_REQUIRES_REPLACE_FILES=${BS_TRUE}
    else
        __ZYPPER_REQUIRES_REPLACE_FILES=${BS_FALSE}
    fi
}

__zypper() {
    zypper --non-interactive "${@}"; return $?
}

__zypper_install() {
    if [ "${__ZYPPER_REQUIRES_REPLACE_FILES}" = "-1" ]; then
        __version_lte "1.10.4" "$(zypper --version | awk '{ print $2 }')"
    fi
    if [ "${__ZYPPER_REQUIRES_REPLACE_FILES}" = "${BS_TRUE}" ]; then
        # In case of file conflicts replace old files.
        # Option present in zypper 1.10.4 and newer:
        # https://github.com/openSUSE/zypper/blob/95655728d26d6d5aef7796b675f4cc69bc0c05c0/package/zypper.changes#L253
        __zypper install --auto-agree-with-licenses --replacefiles "${@}"; return $?
    else
        __zypper install --auto-agree-with-licenses "${@}"; return $?
    fi
}

install_opensuse_stable_deps() {
    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Is the repository already known
        __set_suse_pkg_repo
        # Check zypper repos and refresh if necessary
        __check_and_refresh_suse_pkg_repo
    fi

    __zypper --gpg-auto-import-keys refresh
    if [ $? -ne 0 ] && [ $? -ne 4 ]; then
        # If the exit code is not 0, and it's not 4 (failed to update a
        # repository) return a failure. Otherwise continue.
        return 1
    fi

    if [ "$DISTRO_MAJOR_VERSION" -eq 12 ] && [ "$DISTRO_MINOR_VERSION" -eq 3 ]; then
        # Because patterns-openSUSE-minimal_base-conflicts conflicts with python, lets remove the first one
        __zypper remove patterns-openSUSE-minimal_base-conflicts
    fi

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # YAML module is used for generating custom master/minion configs
    # requests is still used by many salt modules
    # Salt needs python-zypp installed in order to use the zypper module
    __PACKAGES="python-PyYAML python-requests python-zypp"

    # shellcheck disable=SC2086
    __zypper_install ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_opensuse_git_deps() {
    if [ "$_INSECURE_DL" -eq $BS_FALSE ] && [ "${_SALT_REPO_URL%%://*}" = "https" ]; then
        __zypper_install ca-certificates || return 1
    fi

    install_opensuse_stable_deps || return 1

    if ! __check_command_exists git; then
        __zypper_install git  || return 1
    fi

    __zypper_install patch || return 1

    __git_clone_and_checkout || return 1

    __PACKAGES="libzmq5 python-Jinja2 python-msgpack-python python-pycrypto python-pyzmq python-xml"

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __PACKAGES="${__PACKAGES} python-tornado"
        fi
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # shellcheck disable=SC2086
    __zypper_install ${__PACKAGES} || return 1

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_opensuse_stable() {
    __PACKAGES=""

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ];then
        __PACKAGES="${__PACKAGES} salt-cloud"
    fi
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-master"
    fi
    if [ "$_INSTALL_MINION" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-minion"
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} salt-syndic"
    fi

    # shellcheck disable=SC2086
    __zypper_install $__PACKAGES || return 1

    return 0
}

install_opensuse_git() {
    python setup.py ${SETUP_PY_INSTALL_ARGS} install --prefix=/usr || return 1
    return 0
}

install_opensuse_stable_post() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            systemctl is-enabled salt-$fname.service || (systemctl preset salt-$fname.service && systemctl enable salt-$fname.service)
            sleep 0.1
            systemctl daemon-reload
            continue
        fi

        /sbin/chkconfig --add salt-$fname
        /sbin/chkconfig salt-$fname on
    done

    return 0
}

install_opensuse_git_post() {
    for fname in api master minion syndic; do
        # Skip if not meant to be installed
        [ $fname = "api" ] && \
            ([ "$_INSTALL_MASTER" -eq $BS_FALSE ] || ! __check_command_exists "salt-${fname}") && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            use_usr_lib=$BS_FALSE

            if [ "${DISTRO_MAJOR_VERSION}" -gt 13 ] || ([ "${DISTRO_MAJOR_VERSION}" -eq 13 ] && [ "${DISTRO_MINOR_VERSION}" -ge 2 ]); then
                use_usr_lib=$BS_TRUE
            fi

            if [ "${DISTRO_MAJOR_VERSION}" -eq 12 ] && [ -d "/usr/lib/systemd/" ]; then
                use_usr_lib=$BS_TRUE
            fi

            if [ "${use_usr_lib}" -eq $BS_TRUE ]; then
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/usr/lib/systemd/system/salt-${fname}.service"
            else
                __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/salt-${fname}.service" "/lib/systemd/system/salt-${fname}.service"
            fi

            continue
        fi

        __copyfile "${_SALT_GIT_CHECKOUT_DIR}/pkg/rpm/salt-$fname" "/etc/init.d/salt-$fname"
        chmod +x /etc/init.d/salt-$fname
    done

    install_opensuse_stable_post || return 1

    return 0
}

install_opensuse_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -f /bin/systemctl ]; then
            systemctl stop salt-$fname > /dev/null 2>&1
            systemctl start salt-$fname.service
            continue
        fi

        service salt-$fname stop > /dev/null 2>&1
        service salt-$fname start
    done
}

install_opensuse_check_services() {
    if [ ! -f /bin/systemctl ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __check_services_systemd salt-$fname > /dev/null 2>&1 || __check_services_systemd salt-$fname.service > /dev/null 2>&1 || return 1
    done

    return 0
}
#
#   End of openSUSE Install Functions.
#
#######################################################################################################################

#######################################################################################################################
#
#   SUSE Enterprise 12
#

install_suse_12_stable_deps() {
    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Is the repository already known
        __set_suse_pkg_repo
        # Check zypper repos and refresh if necessary
        __check_and_refresh_suse_pkg_repo
    fi

    __zypper --gpg-auto-import-keys refresh || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # YAML module is used for generating custom master/minion configs
    # requests is still used by many salt modules
    # Salt needs python-zypp installed in order to use the zypper module
    __PACKAGES="python-PyYAML python-requests python-zypp"

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # shellcheck disable=SC2086,SC2090
    __zypper_install ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_suse_12_git_deps() {
    install_suse_12_stable_deps || return 1

    if ! __check_command_exists git; then
        __zypper_install git  || return 1
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES=""
    # shellcheck disable=SC2089
    __PACKAGES="${__PACKAGES} libzmq3 python-Jinja2 python-msgpack-python python-pycrypto"
    __PACKAGES="${__PACKAGES} python-pyzmq python-xml"

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __PACKAGES="${__PACKAGES} python-tornado"
        fi
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # shellcheck disable=SC2086
    __zypper_install ${__PACKAGES} || return 1

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_suse_12_stable() {
    install_opensuse_stable || return 1
    return 0
}

install_suse_12_git() {
    install_opensuse_git || return 1
    return 0
}

install_suse_12_stable_post() {
    install_opensuse_stable_post || return 1
    return 0
}

install_suse_12_git_post() {
    install_opensuse_git_post || return 1
    return 0
}

install_suse_12_restart_daemons() {
    install_opensuse_restart_daemons || return 1
    return 0
}

#
#   End of SUSE Enterprise 12
#
#######################################################################################################################

#######################################################################################################################
#
#   SUSE Enterprise 11
#

install_suse_11_stable_deps() {
    if [ $_DISABLE_REPOS -eq $BS_FALSE ]; then
        # Is the repository already known
        __set_suse_pkg_repo
        # Check zypper repos and refresh if necessary
        __check_and_refresh_suse_pkg_repo
    fi

    __zypper --gpg-auto-import-keys refresh || return 1

    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        __zypper --gpg-auto-import-keys update || return 1
    fi

    # YAML module is used for generating custom master/minion configs
    __PACKAGES="python-PyYAML"

    # shellcheck disable=SC2086,SC2090
    __zypper_install ${__PACKAGES} || return 1

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __zypper_install ${_EXTRA_PACKAGES} || return 1
    fi

    return 0
}

install_suse_11_git_deps() {
    install_suse_11_stable_deps || return 1

    if ! __check_command_exists git; then
        __zypper_install git  || return 1
    fi

    __git_clone_and_checkout || return 1

    __PACKAGES=""
    # shellcheck disable=SC2089
    __PACKAGES="${__PACKAGES} libzmq4 python-Jinja2 python-msgpack-python python-pycrypto"
    __PACKAGES="${__PACKAGES} python-pyzmq python-xml python-zypp"

    if [ -f "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt" ]; then
        # We're on the develop branch, install whichever tornado is on the requirements file
        __REQUIRED_TORNADO="$(grep tornado "${_SALT_GIT_CHECKOUT_DIR}/requirements/base.txt")"
        if [ "${__REQUIRED_TORNADO}" != "" ]; then
            __PACKAGES="${__PACKAGES} python-tornado"
        fi
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __PACKAGES="${__PACKAGES} python-apache-libcloud"
    fi

    # shellcheck disable=SC2086
    __zypper_install ${__PACKAGES} || return 1

    # Let's trigger config_salt()
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="${_SALT_GIT_CHECKOUT_DIR}/conf/"
        CONFIG_SALT_FUNC="config_salt"
    fi

    return 0
}

install_suse_11_stable() {
    install_opensuse_stable || return 1
    return 0
}

install_suse_11_git() {
    install_opensuse_git || return 1
    return 0
}

install_suse_11_stable_post() {
    install_opensuse_stable_post || return 1
    return 0
}

install_suse_11_git_post() {
    install_opensuse_git_post || return 1
    return 0
}

install_suse_11_restart_daemons() {
    install_opensuse_restart_daemons || return 1
    return 0
}


#
#   End of SUSE Enterprise 11
#
#######################################################################################################################

#######################################################################################################################
#
# SUSE Enterprise General Functions
#

# Used for both SLE 11 and 12
install_suse_check_services() {
    if [ ! -f /bin/systemctl ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __check_services_systemd salt-$fname || return 1
    done

    return 0
}

#
#   End of SUSE Enterprise General Functions
#
#######################################################################################################################

#######################################################################################################################
#
#    Gentoo Install Functions.
#
__autounmask() {
    emerge --autounmask-write --autounmask-only "${@}"; return $?
}

__emerge() {
    if [ "$_GENTOO_USE_BINHOST" -eq $BS_TRUE ]; then
        emerge --getbinpkg "${@}"; return $?
    fi
    emerge "${@}"; return $?
}

__gentoo_config_protection() {
    # usually it's a good thing to have config files protected by portage, but
    # in this case this would require to interrupt the bootstrapping script at
    # this point, manually merge the changes using etc-update/dispatch-conf/
    # cfg-update and then restart the bootstrapping script, so instead we allow
    # at this point to modify certain config files directly
    export CONFIG_PROTECT_MASK="${CONFIG_PROTECT_MASK:-} /etc/portage/package.accept_keywords /etc/portage/package.keywords /etc/portage/package.license /etc/portage/package.unmask /etc/portage/package.use"

    # emerge currently won't write to files that aren't there, so we need to ensure their presence
    touch /etc/portage/package.accept_keywords /etc/portage/package.keywords /etc/portage/package.license /etc/portage/package.unmask /etc/portage/package.use
}

__gentoo_pre_dep() {
    if [ "$_ECHO_DEBUG" -eq $BS_TRUE ]; then
        if __check_command_exists eix; then
            eix-sync
        else
            emerge --sync
        fi
    else
        if __check_command_exists eix; then
            eix-sync -q
        else
            emerge --sync --quiet
        fi
    fi
    if [ ! -d /etc/portage ]; then
        mkdir /etc/portage
    fi
}

__gentoo_post_dep() {
    # ensures dev-lib/crypto++ compiles happily
    __emerge --oneshot 'sys-devel/libtool'
    # the -o option asks it to emerge the deps but not the package.
    __gentoo_config_protection

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        __autounmask 'dev-python/libcloud'
        __emerge -v 'dev-python/libcloud'
    fi

    __autounmask 'dev-python/requests'
    __autounmask 'app-admin/salt'

    __emerge -vo 'dev-python/requests'
    __emerge -vo 'app-admin/salt'

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        # shellcheck disable=SC2086
        __autounmask ${_EXTRA_PACKAGES} || return 1
        # shellcheck disable=SC2086
        __emerge -v ${_EXTRA_PACKAGES} || return 1
    fi
}

install_gentoo_deps() {
    __gentoo_pre_dep || return 1
    __gentoo_post_dep || return 1
}

install_gentoo_git_deps() {
    __gentoo_pre_dep || return 1
    __gentoo_post_dep || return 1
}

install_gentoo_stable() {
    __gentoo_config_protection
    __emerge -v 'app-admin/salt' || return 1
}

install_gentoo_git() {
    __gentoo_config_protection
    __emerge -v '=app-admin/salt-9999' || return 1
}

install_gentoo_post() {
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -d "/run/systemd/system" ]; then
            systemctl enable salt-$fname.service
            systemctl start salt-$fname.service
        else
            rc-update add salt-$fname default
            /etc/init.d/salt-$fname start
        fi
    done
}

install_gentoo_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ -d "/run/systemd/system" ]; then
            systemctl stop salt-$fname > /dev/null 2>&1
            systemctl start salt-$fname.service
        else
            /etc/init.d/salt-$fname stop > /dev/null 2>&1
            /etc/init.d/salt-$fname start
        fi
    done
}

install_gentoo_check_services() {
    if [ ! -d "/run/systemd/system" ]; then
        # Not running systemd!? Don't check!
        return 0
    fi

    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        __check_services_systemd salt-$fname || return 1
    done

    return 0
}
#
#   End of Gentoo Install Functions.
#
#######################################################################################################################

#######################################################################################################################
#
#   VoidLinux Install Functions
#
install_voidlinux_stable_deps() {
    if [ "$_UPGRADE_SYS" -eq $BS_TRUE ]; then
        xbps-install -Suy || return 1
    fi

    if [ "${_EXTRA_PACKAGES}" != "" ]; then
        echoinfo "Installing the following extra packages as requested: ${_EXTRA_PACKAGES}"
        xbps-install -Suy "${_EXTRA_PACKAGES}" || return 1
    fi

    return 0
}

install_voidlinux_stable() {
    xbps-install -Suy salt || return 1
    return 0
}

install_voidlinux_stable_post() {
    for fname in master minion syndic; do
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        ln -s /etc/sv/salt-$fname /var/service/.
    done
}

install_voidlinux_restart_daemons() {
    [ $_START_DAEMONS -eq $BS_FALSE ] && return

    for fname in master minion syndic; do
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        sv restart salt-$fname
    done
}

install_voidlinux_check_services() {
    for fname in master minion syndic; do
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        [ -e /var/service/salt-$fname ] || return 1
    done

    return 0
}

daemons_running_voidlinux() {
    [ "$_START_DAEMONS" -eq $BS_FALSE ] && return 0

    FAILED_DAEMONS=0
    for fname in master minion syndic; do
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        if [ "$(sv status salt-$fname | grep run)" = "" ]; then
            echoerror "salt-$fname was not found running"
            FAILED_DAEMONS=$((FAILED_DAEMONS + 1))
        fi
    done

    return $FAILED_DAEMONS
}
#
#   Ended VoidLinux Install Functions
#
#######################################################################################################################

#######################################################################################################################
#
#   Default minion configuration function. Matches ANY distribution as long as
#   the -c options is passed.
#
config_salt() {
    # If the configuration directory is not passed, return
    [ "$_TEMP_CONFIG_DIR" = "null" ] && return

    if [ "$_CONFIG_ONLY" -eq $BS_TRUE ]; then
        echowarn "Passing -C (config only) option implies -F (forced overwrite)."

        if [ "$_FORCE_OVERWRITE" -ne $BS_TRUE ]; then
            echowarn "Overwriting configs in 11 seconds!"
            sleep 11
            _FORCE_OVERWRITE=$BS_TRUE
        fi
    fi

    # Let's create the necessary directories
    [ -d "$_SALT_ETC_DIR" ] || mkdir "$_SALT_ETC_DIR" || return 1
    [ -d "$_PKI_DIR" ] || (mkdir -p "$_PKI_DIR" && chmod 700 "$_PKI_DIR") || return 1

    # If -C or -F was passed, we don't need a .bak file for the config we're updating
    # This is used in the custom master/minion config file checks below
    CREATE_BAK=$BS_TRUE
    if [ "$_FORCE_OVERWRITE" -eq $BS_TRUE ]; then
        CREATE_BAK=$BS_FALSE
    fi

    CONFIGURED_ANYTHING=$BS_FALSE

    # Copy the grains file if found
    if [ -f "$_TEMP_CONFIG_DIR/grains" ]; then
        echodebug "Moving provided grains file from $_TEMP_CONFIG_DIR/grains to $_SALT_ETC_DIR/grains"
        __movefile "$_TEMP_CONFIG_DIR/grains" "$_SALT_ETC_DIR/grains" || return 1
        CONFIGURED_ANYTHING=$BS_TRUE
    fi

    if [ "$_INSTALL_MINION" -eq $BS_TRUE ] || \
        [ "$_CONFIG_ONLY" -eq $BS_TRUE ] || [ "$_CUSTOM_MINION_CONFIG" != "null" ]; then
        # Create the PKI directory
        [ -d "$_PKI_DIR/minion" ] || (mkdir -p "$_PKI_DIR/minion" && chmod 700 "$_PKI_DIR/minion") || return 1

        # Check to see if a custom minion config json dict was provided
        if [ "$_CUSTOM_MINION_CONFIG" != "null" ]; then

            # Check if a minion config file already exists and move to .bak if needed
            if [ -f "$_SALT_ETC_DIR/minion" ] && [ "$CREATE_BAK" -eq "$BS_TRUE" ]; then
                __movefile "$_SALT_ETC_DIR/minion" "$_SALT_ETC_DIR/minion.bak" $BS_TRUE || return 1
                CONFIGURED_ANYTHING=$BS_TRUE
            fi

            # Overwrite/create the config file with the yaml string
            __overwriteconfig "$_SALT_ETC_DIR/minion" "$_CUSTOM_MINION_CONFIG" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE

        # Copy the minions configuration if found
        # Explicitly check for custom master config to avoid moving the minion config
        elif [ -f "$_TEMP_CONFIG_DIR/minion" ] && [ "$_CUSTOM_MASTER_CONFIG" = "null" ]; then
            __movefile "$_TEMP_CONFIG_DIR/minion" "$_SALT_ETC_DIR" "$_FORCE_OVERWRITE" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi

        # Copy the minion's keys if found
        if [ -f "$_TEMP_CONFIG_DIR/minion.pem" ]; then
            __movefile "$_TEMP_CONFIG_DIR/minion.pem" "$_PKI_DIR/minion/" "$_FORCE_OVERWRITE" || return 1
            chmod 400 "$_PKI_DIR/minion/minion.pem" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        if [ -f "$_TEMP_CONFIG_DIR/minion.pub" ]; then
            __movefile "$_TEMP_CONFIG_DIR/minion.pub" "$_PKI_DIR/minion/" "$_FORCE_OVERWRITE" || return 1
            chmod 664 "$_PKI_DIR/minion/minion.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        # For multi-master-pki, copy the master_sign public key if found
        if [ -f "$_TEMP_CONFIG_DIR/master_sign.pub" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master_sign.pub" "$_PKI_DIR/minion/" || return 1
            chmod 664 "$_PKI_DIR/minion/master_sign.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
    fi

    # only (re)place master or syndic configs if -M (install master) or -S
    # (install syndic) specified
    OVERWRITE_MASTER_CONFIGS=$BS_FALSE
    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ] && [ "$_CONFIG_ONLY" -eq $BS_TRUE ]; then
        OVERWRITE_MASTER_CONFIGS=$BS_TRUE
    fi
    if [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ] && [ "$_CONFIG_ONLY" -eq $BS_TRUE ]; then
        OVERWRITE_MASTER_CONFIGS=$BS_TRUE
    fi

    if [ "$_INSTALL_MASTER" -eq $BS_TRUE ] || [ "$_INSTALL_SYNDIC" -eq $BS_TRUE ] || [ "$OVERWRITE_MASTER_CONFIGS" -eq $BS_TRUE ] || [ "$_CUSTOM_MASTER_CONFIG" != "null" ]; then
        # Create the PKI directory
        [ -d "$_PKI_DIR/master" ] || (mkdir -p "$_PKI_DIR/master" && chmod 700 "$_PKI_DIR/master") || return 1

        # Check to see if a custom master config json dict was provided
        if [ "$_CUSTOM_MASTER_CONFIG" != "null" ]; then

            # Check if a master config file already exists and move to .bak if needed
            if [ -f "$_SALT_ETC_DIR/master" ] && [ "$CREATE_BAK" -eq "$BS_TRUE" ]; then
                __movefile "$_SALT_ETC_DIR/master" "$_SALT_ETC_DIR/master.bak" $BS_TRUE || return 1
                CONFIGURED_ANYTHING=$BS_TRUE
            fi

            # Overwrite/create the config file with the yaml string
            __overwriteconfig "$_SALT_ETC_DIR/master" "$_CUSTOM_MASTER_CONFIG" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE

        # Copy the masters configuration if found
        elif [ -f "$_TEMP_CONFIG_DIR/master" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master" "$_SALT_ETC_DIR" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi

        # Copy the master's keys if found
        if [ -f "$_TEMP_CONFIG_DIR/master.pem" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master.pem" "$_PKI_DIR/master/" || return 1
            chmod 400 "$_PKI_DIR/master/master.pem" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
        if [ -f "$_TEMP_CONFIG_DIR/master.pub" ]; then
            __movefile "$_TEMP_CONFIG_DIR/master.pub" "$_PKI_DIR/master/" || return 1
            chmod 664 "$_PKI_DIR/master/master.pub" || return 1
            CONFIGURED_ANYTHING=$BS_TRUE
        fi
    fi

    if [ "$_INSTALL_CLOUD" -eq $BS_TRUE ]; then
        # Recursively copy salt-cloud configs with overwriting if necessary
        for file in "$_TEMP_CONFIG_DIR"/cloud*; do
            if [ -f "$file" ]; then
                __copyfile "$file" "$_SALT_ETC_DIR" || return 1
            elif [ -d "$file" ]; then
                subdir="$(basename "$file")"
                mkdir -p "$_SALT_ETC_DIR/$subdir"
                for file_d in "$_TEMP_CONFIG_DIR/$subdir"/*; do
                    if [ -f "$file_d" ]; then
                        __copyfile "$file_d" "$_SALT_ETC_DIR/$subdir" || return 1
                    fi
                done
            fi
        done
    fi

    if [ "$_CONFIG_ONLY" -eq $BS_TRUE ] && [ $CONFIGURED_ANYTHING -eq $BS_FALSE ]; then
        echowarn "No configuration or keys were copied over. No configuration was done!"
        exit 0
    fi

    return 0
}
#
#  Ended Default Configuration function
#
#######################################################################################################################

#######################################################################################################################
#
#   Default salt master minion keys pre-seed function. Matches ANY distribution
#   as long as the -k option is passed.
#
preseed_master() {
    # Create the PKI directory

    if [ "$(find "$_TEMP_KEYS_DIR" -maxdepth 1 -type f | wc -l)" -lt 1 ]; then
        echoerror "No minion keys were uploaded. Unable to pre-seed master"
        return 1
    fi

    SEED_DEST="$_PKI_DIR/master/minions"
    [ -d "$SEED_DEST" ] || (mkdir -p "$SEED_DEST" && chmod 700 "$SEED_DEST") || return 1

    for keyfile in $_TEMP_KEYS_DIR/*; do
        keyfile=$(basename "${keyfile}")
        src_keyfile="${_TEMP_KEYS_DIR}/${keyfile}"
        dst_keyfile="${SEED_DEST}/${keyfile}"

        # If it's not a file, skip to the next
        [ ! -f "$src_keyfile" ] && continue

        __movefile "$src_keyfile" "$dst_keyfile" || return 1
        chmod 664 "$dst_keyfile" || return 1
    done

    return 0
}
#
#  Ended Default Salt Master Pre-Seed minion keys function
#
#######################################################################################################################

#######################################################################################################################
#
#   This function checks if all of the installed daemons are running or not.
#
daemons_running() {
    [ "$_START_DAEMONS" -eq $BS_FALSE ] && return 0

    FAILED_DAEMONS=0
    for fname in api master minion syndic; do
        # Skip salt-api since the service should be opt-in and not necessarily started on boot
        [ $fname = "api" ] && continue

        # Skip if not meant to be installed
        [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
        [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
        [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

        # shellcheck disable=SC2009
        if [ "${DISTRO_NAME}" = "SmartOS" ]; then
            if [ "$(svcs -Ho STA salt-$fname)" != "ON" ]; then
                echoerror "salt-$fname was not found running"
                FAILED_DAEMONS=$((FAILED_DAEMONS + 1))
            fi
        elif [ "$(ps wwwaux | grep -v grep | grep salt-$fname)" = "" ]; then
            echoerror "salt-$fname was not found running"
            FAILED_DAEMONS=$((FAILED_DAEMONS + 1))
        fi
    done

    return $FAILED_DAEMONS
}
#
#  Ended daemons running check function
#
#######################################################################################################################

#======================================================================================================================
# LET'S PROCEED WITH OUR INSTALLATION
#======================================================================================================================

# Let's get the dependencies install function
if [ ${_NO_DEPS} -eq $BS_FALSE ]; then
    DEP_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_deps"
    DEP_FUNC_NAMES="$DEP_FUNC_NAMES install_${DISTRO_NAME_L}_deps"
elif [ "${ITYPE}" = "git" ]; then
    DEP_FUNC_NAMES="__git_clone_and_checkout"
else
    DEP_FUNC_NAMES=""
fi

DEPS_INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$DEP_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        DEPS_INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "DEPS_INSTALL_FUNC=${DEPS_INSTALL_FUNC}"

# Let's get the Salt config function
CONFIG_FUNC_NAMES="config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_salt"
CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_salt"
CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_salt"
CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_salt"
CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}_${ITYPE}_salt"
CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_${DISTRO_NAME_L}_salt"
CONFIG_FUNC_NAMES="$CONFIG_FUNC_NAMES config_salt"

CONFIG_SALT_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$CONFIG_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        CONFIG_SALT_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "CONFIG_SALT_FUNC=${CONFIG_SALT_FUNC}"

# Let's get the pre-seed master function
PRESEED_FUNC_NAMES="preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_master"
PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_master"
PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_master"
PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_master"
PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}_${ITYPE}_master"
PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_${DISTRO_NAME_L}_master"
PRESEED_FUNC_NAMES="$PRESEED_FUNC_NAMES preseed_master"

PRESEED_MASTER_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$PRESEED_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        PRESEED_MASTER_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "PRESEED_MASTER_FUNC=${PRESEED_MASTER_FUNC}"

# Let's get the install function
INSTALL_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}"
INSTALL_FUNC_NAMES="$INSTALL_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}"
INSTALL_FUNC_NAMES="$INSTALL_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}"

INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$INSTALL_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "INSTALL_FUNC=${INSTALL_FUNC}"

# Let's get the post install function
POST_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_post"
POST_FUNC_NAMES="$POST_FUNC_NAMES install_${DISTRO_NAME_L}_post"

POST_INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$POST_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        POST_INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "POST_INSTALL_FUNC=${POST_INSTALL_FUNC}"

# Let's get the start daemons install function
STARTDAEMONS_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_restart_daemons"
STARTDAEMONS_FUNC_NAMES="$STARTDAEMONS_FUNC_NAMES install_${DISTRO_NAME_L}_restart_daemons"

STARTDAEMONS_INSTALL_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$STARTDAEMONS_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        STARTDAEMONS_INSTALL_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "STARTDAEMONS_INSTALL_FUNC=${STARTDAEMONS_INSTALL_FUNC}"

# Let's get the daemons running check function.
DAEMONS_RUNNING_FUNC_NAMES="daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}_${ITYPE}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running_${DISTRO_NAME_L}"
DAEMONS_RUNNING_FUNC_NAMES="$DAEMONS_RUNNING_FUNC_NAMES daemons_running"

DAEMONS_RUNNING_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$DAEMONS_RUNNING_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        DAEMONS_RUNNING_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "DAEMONS_RUNNING_FUNC=${DAEMONS_RUNNING_FUNC}"

# Let's get the check services function
if [ ${_DISABLE_SALT_CHECKS} -eq $BS_FALSE ]; then
    CHECK_SERVICES_FUNC_NAMES="install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_${ITYPE}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_${ITYPE}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}${PREFIXED_DISTRO_MAJOR_VERSION}${PREFIXED_DISTRO_MINOR_VERSION}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}_${ITYPE}_check_services"
    CHECK_SERVICES_FUNC_NAMES="$CHECK_SERVICES_FUNC_NAMES install_${DISTRO_NAME_L}_check_services"
else
    CHECK_SERVICES_FUNC_NAMES=""
fi

CHECK_SERVICES_FUNC="null"
for FUNC_NAME in $(__strip_duplicates "$CHECK_SERVICES_FUNC_NAMES"); do
    if __function_defined "$FUNC_NAME"; then
        CHECK_SERVICES_FUNC="$FUNC_NAME"
        break
    fi
done
echodebug "CHECK_SERVICES_FUNC=${CHECK_SERVICES_FUNC}"

if [ ${_NO_DEPS} -eq $BS_FALSE ] && [ "$DEPS_INSTALL_FUNC" = "null" ]; then
    echoerror "No dependencies installation function found. Exiting..."
    exit 1
fi

if [ "$INSTALL_FUNC" = "null" ]; then
    echoerror "No installation function found. Exiting..."
    exit 1
fi

# Install dependencies
if [ ${_NO_DEPS} -eq $BS_FALSE ] && [ $_CONFIG_ONLY -eq $BS_FALSE ]; then
    # Only execute function is not in config mode only
    echoinfo "Running ${DEPS_INSTALL_FUNC}()"
    $DEPS_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${DEPS_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Triggering config_salt() if overwriting master or minion configs
if [ "$_CUSTOM_MASTER_CONFIG" != "null" ] || [ "$_CUSTOM_MINION_CONFIG" != "null" ]; then
    if [ "$_TEMP_CONFIG_DIR" = "null" ]; then
        _TEMP_CONFIG_DIR="$_SALT_ETC_DIR"
    fi

    if [ ${_NO_DEPS} -eq $BS_FALSE ] && [ $_CONFIG_ONLY -eq $BS_TRUE ]; then
        # Execute function to satisfy dependencies for configuration step
        echoinfo "Running ${DEPS_INSTALL_FUNC}()"
        $DEPS_INSTALL_FUNC
        if [ $? -ne 0 ]; then
            echoerror "Failed to run ${DEPS_INSTALL_FUNC}()!!!"
            exit 1
        fi
    fi
fi

# Configure Salt
if [ "$CONFIG_SALT_FUNC" != "null" ] && [ "$_TEMP_CONFIG_DIR" != "null" ]; then
    echoinfo "Running ${CONFIG_SALT_FUNC}()"
    $CONFIG_SALT_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${CONFIG_SALT_FUNC}()!!!"
        exit 1
    fi
fi

# Drop the master address if passed
if [ "$_SALT_MASTER_ADDRESS" != "null" ]; then
    [ ! -d "$_SALT_ETC_DIR/minion.d" ] && mkdir -p "$_SALT_ETC_DIR/minion.d"
    cat <<_eof > $_SALT_ETC_DIR/minion.d/99-master-address.conf
master: $_SALT_MASTER_ADDRESS
_eof
fi

# Drop the minion id if passed
if [ "$_SALT_MINION_ID" != "null" ]; then
    [ ! -d "$_SALT_ETC_DIR" ] && mkdir -p "$_SALT_ETC_DIR"
    echo "$_SALT_MINION_ID" > "$_SALT_ETC_DIR/minion_id"
fi

# Pre-seed master keys
if [ "$PRESEED_MASTER_FUNC" != "null" ] && [ "$_TEMP_KEYS_DIR" != "null" ]; then
    echoinfo "Running ${PRESEED_MASTER_FUNC}()"
    $PRESEED_MASTER_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${PRESEED_MASTER_FUNC}()!!!"
        exit 1
    fi
fi

# Install Salt
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    # Only execute function is not in config mode only
    echoinfo "Running ${INSTALL_FUNC}()"
    $INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Run any post install function. Only execute function if not in config mode only
if [ "$POST_INSTALL_FUNC" != "null" ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echoinfo "Running ${POST_INSTALL_FUNC}()"
    $POST_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${POST_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Run any check services function, Only execute function if not in config mode only
if [ "$CHECK_SERVICES_FUNC" != "null" ] && [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echoinfo "Running ${CHECK_SERVICES_FUNC}()"
    $CHECK_SERVICES_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${CHECK_SERVICES_FUNC}()!!!"
        exit 1
    fi
fi

# Run any start daemons function
if [ "$STARTDAEMONS_INSTALL_FUNC" != "null" ] && [ ${_START_DAEMONS} -eq $BS_TRUE ]; then
    echoinfo "Running ${STARTDAEMONS_INSTALL_FUNC}()"
    echodebug "Waiting ${_SLEEP} seconds for processes to settle before checking for them"
    sleep ${_SLEEP}
    $STARTDAEMONS_INSTALL_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${STARTDAEMONS_INSTALL_FUNC}()!!!"
        exit 1
    fi
fi

# Check if the installed daemons are running or not
if [ "$DAEMONS_RUNNING_FUNC" != "null" ] && [ ${_START_DAEMONS} -eq $BS_TRUE ]; then
    echoinfo "Running ${DAEMONS_RUNNING_FUNC}()"
    echodebug "Waiting ${_SLEEP} seconds for processes to settle before checking for them"
    sleep ${_SLEEP}  # Sleep a little bit to let daemons start
    $DAEMONS_RUNNING_FUNC
    if [ $? -ne 0 ]; then
        echoerror "Failed to run ${DAEMONS_RUNNING_FUNC}()!!!"

        for fname in api master minion syndic; do
            # Skip salt-api since the service should be opt-in and not necessarily started on boot
            [ $fname = "api" ] && continue

            # Skip if not meant to be installed
            [ $fname = "master" ] && [ "$_INSTALL_MASTER" -eq $BS_FALSE ] && continue
            [ $fname = "minion" ] && [ "$_INSTALL_MINION" -eq $BS_FALSE ] && continue
            [ $fname = "syndic" ] && [ "$_INSTALL_SYNDIC" -eq $BS_FALSE ] && continue

            if [ "$_ECHO_DEBUG" -eq $BS_FALSE ]; then
                echoerror "salt-$fname was not found running. Pass '-D' to ${__ScriptName} when bootstrapping for additional debugging information..."
                continue
            fi

            [ ! -f "$_SALT_ETC_DIR/$fname" ] && [ $fname != "syndic" ] && echodebug "$_SALT_ETC_DIR/$fname does not exist"

            echodebug "Running salt-$fname by hand outputs: $(nohup salt-$fname -l debug)"

            [ ! -f /var/log/salt/$fname ] && echodebug "/var/log/salt/$fname does not exist. Can't cat its contents!" && continue

            echodebug "DAEMON LOGS for $fname:"
            echodebug "$(cat /var/log/salt/$fname)"
            echo
        done

        echodebug "Running Processes:"
        echodebug "$(ps auxwww)"

        exit 1
    fi
fi

# Done!
if [ "$_CONFIG_ONLY" -eq $BS_FALSE ]; then
    echoinfo "Salt installed!"
else
    echoinfo "Salt configured!"
fi

exit 0
