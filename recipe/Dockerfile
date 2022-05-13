FROM quay.io/condaforge/linux-anvil-cuda:11.2

ENV CONFIG="linux_64_c_compiler_version10cuda_compiler_version11.2cudnn8cxx_compiler_version10python3.9.____cpython"

ENV UPLOAD_PACKAGES="False"
ENV IS_PR_BUILD="True"
ENV BUILD_WITH_CONDA_DEBUG="0"
ENV MINIFORGE_HOME="./miniforge3"

RUN \
    set -xeo pipefail \
    THISDIR="$( cd "$( dirname "$0" )" >/dev/null && pwd )" \
    PROVIDER_DIR="$(basename $THISDIR)" \
    FEEDSTOCK_ROOT="$( cd "$( dirname "$0" )/.." >/dev/null && pwd )" \
    RECIPE_ROOT="${FEEDSTOCK_ROOT}/recipe" \
    if [ -z ${FEEDSTOCK_NAME} ]; then \
        export FEEDSTOCK_NAME=$(basename ${FEEDSTOCK_ROOT}) \
    fi \
    ARTIFACTS="$FEEDSTOCK_ROOT/build_artifacts" \
    mkdir -p "$ARTIFACTS" \
    DONE_CANARY="$ARTIFACTS/conda-forge-build-done-${CONFIG}" \
    rm -f "$DONE_CANARY" \
    export UPLOAD_PACKAGES="${UPLOAD_PACKAGES:-True}" \
    export IS_PR_BUILD="${IS_PR_BUILD:-False}" \
    docker pull "${DOCKER_IMAGE}"
    bash \
        "/home/conda/feedstock_root/${PROVIDER_DIR}/build_steps.sh" \
    test -f "$DONE_CANARY"
