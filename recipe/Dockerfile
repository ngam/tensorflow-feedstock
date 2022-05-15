FROM quay.io/condaforge/linux-anvil-cuda:11.2

ENV CONFIG="linux_64_c_compiler_version10cuda_compiler_version11.2cudnn8cxx_compiler_version10python3.9.____cpython"

ENV UPLOAD_PACKAGES="False"
ENV IS_PR_BUILD="True"
ENV BUILD_WITH_CONDA_DEBUG="0"
ENV MINIFORGE_HOME="./miniforge3"

ADD . /home/conda/feedstock_root/
RUN /home/conda/feedstock_root/.scripts/build_steps.sh
