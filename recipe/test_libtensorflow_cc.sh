#!/bin/bash

set -exuo pipefail

${CXX} ${CXXFLAGS} ${LDFLAGS} -o test_cc -ltensorflow_cc -ltensorflow_framework -lrt test_cc.cc
./test_cc
