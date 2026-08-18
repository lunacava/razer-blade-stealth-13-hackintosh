#!/bin/bash
ioreg -r -c AppleBacklightDisplay -d1 -w0 2>/dev/null \
  | tr -d ' ' | sed -n 's/.*"bklt"={"min"=\([0-9]*\),"max"=\([0-9]*\),"value"=\([0-9]*\)}.*/bklt = \3 \/ \2/p'
