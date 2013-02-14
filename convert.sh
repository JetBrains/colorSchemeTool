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
    echo converting $DIR$FN$EXT to $OUTDIR$BASE.xml ...
	python colorSchemeTool.py $FILE $OUTDIR$BASE.xml >> ./colorSchemeTool.log
done
