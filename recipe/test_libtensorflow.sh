#!/bin/bash

set -euxo pipefail

${CC} -o test_c ${CFLAGS} ${LDFLAGS} test_c.c -ltensorflow
./test_c
