#!/bin/bash

set -exuo pipefail

if [[ "${target_platform}" == linux-* ]]; then
  export LDFLAGS="${LDFLAGS} -lrt"
fi
${CXX} ${CXXFLAGS} ${LDFLAGS} -o test_cc test_cc.cc -ltensorflow_cc -ltensorflow_framework
./test_cc
