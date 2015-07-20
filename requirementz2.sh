#!/bin/bash

# ...Runs requirementz with the python 2.7 interpreter to use pip2.
# -Christopher Welborn 07-19-2015
# appname="requirementz2"
# appversion="0.0.1"
apppath="$(readlink -f "${BASH_SOURCE[0]}")"
appdir="${apppath%/*}"

pyexes=("python2" "python2.7" "python-2.7")
pyexe=""
let exitcode=1
for tryexe in "${pyexes[@]}"
do
    pyexe="$(which "$tryexe")"
    if [[ -n "$pyexe" ]]; then
        "$pyexe" "$appdir/requirementz.py" "$@"
        let exitcode="$?"
        break
    fi
done

if [[ -z "$pyexe" ]]; then
    echo "Unable to locate a suitable python2 executable!"
    let exitcode=1
fi

exit $exitcode
