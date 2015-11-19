#!/bin/bash

FILES=./tmThemes/*.tmTheme
OUTDIR=./intellijThemes/

shopt -s nullglob

for FILE in $FILES
do
    FN="${FILE##*/}"
    DIR="${FILE:0:${#FILE} - ${#FN}}"
    BASE="${FN%.[^.]*}"
    EXT="${FN:${#BASE} + 1}"
    echo converting $DIR$FN$EXT to $OUTDIR$BASE.icls ...
	python colorSchemeTool.py $FILE $OUTDIR$BASE.icls >> ./colorSchemeTool.log
done
