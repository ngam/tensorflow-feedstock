#!/bin/bash

set -euxo pipefail

${CC} -o test_c ${CFLAGS} ${LDFLAGS} -ltensorflow test_c.c
./test_c
