from pathlib import Path
from shutil import copyfile
from glob import glob as py_glob
import requests
import os
import re

# TODO: Automatically extract this
llvm_commit = "55c71c9eac9bc7f956a05fa9258fad4f86565450"
Path("llvm-project/llvm").mkdir(exist_ok=True, parents=True)
Path("llvm-project/mlir").mkdir(exist_ok=True, parents=True)

# Shared code between LLVM and MLIR bazel generation

def empty(*args, **kwargs):
    pass

def cc_library(name, deps=None, *args, **kwargs):
    global output
    if deps is None:
        deps = []
    # Remove third-party dependencies
    # filtered_deps = [dep for dep in deps if (not dep.startswith("@llvm_"))]
    filtered_deps = [dep for dep in deps if dep[1:] in LLVM_LIBS]
    output += f"""
cc_library(
    name = "{name}",
    linkopts = {make_linkopts(name)},
    visibility = ["//visibility:public"],
    deps = {filtered_deps},
)"""

def import_file(f):
    p = Path(f)
    target = Path("llvm-project") / SYMBOL.lower() / p
    target.parent.mkdir(parents=True, exist_ok=True)
    origin = PREFIX / p
    copyfile(origin, target)

def glob(search, **kwargs):
    out = []
    for a in search:
        out += py_glob(a, root_dir=os.environ["PREFIX"])
    return out

def exports_files(files):
    global output
    for f in files:
        if f in ["LICENSE.TXT", "run_lit.sh", "include/llvm/Config/config.h.cmake", "include/llvm/Config/llvm-config.h.cmake", "include/llvm/Config/abi-breaking.h.cmake"]:
            continue
        import_file(f)
    output += f"""
exports_files(
    {files}
)
"""


# Generate LLVM build defintion

PREFIX = Path(os.environ["PREFIX"])
SYMBOL = "LLVM"

def make_linkopts(name):
    # TODO: More strategies
    #   1. If the lib doesn't exist, try to find a more global, e.g. QuantOps -> Quant
    #   2. Otherwise, add all MLIR libs and trust --as-needed linkage
    if name == "Support":
        return [f"-lLLVM{l}" for l in LLVM_LIBS]
    libname = f"lib{SYMBOL}{name}.a"
    upper_match = re.search("(.*)([A-Z][a-z]*)$", name)
    if (PREFIX / "lib" / libname).exists():
        return [f"-l{SYMBOL}{name}"]
    elif (PREFIX / "lib" / libname.replace("Dialect", "IR")).exists():
        return [f"-l{SYMBOL}{name.replace('Dialect', 'IR')}"]
    elif upper_match is not None:
        name = upper_match.group(1)
        if len(name) > 1:
            return make_linkopts(name)
    return []


libdir = Path(os.environ["PREFIX"]) / "lib"

output = """
exports_files([\"LICENSE.TXT\"])
"""

r = requests.get(f"https://raw.githubusercontent.com/llvm/llvm-project/{llvm_commit}/utils/bazel/llvm-project-overlay/llvm/BUILD.bazel")

LLVM_LIBS = []

llvm_libs = libdir.glob("libLLVM*.a")
llvm_build = "exports_files([\"LICENSE.TXT\"])"
for lib in llvm_libs:
    basename = lib.name[7:-2]
    LLVM_LIBS.append(basename)

sh_binary = py_binary = binary_alias = filegroup = gentbl = cc_binary = template_rule = genrule = enum_targets_gen = package = load = empty
llvm_config_defines = []
llvm_targets = []

def select(*args, **kwargs):
    return []

# Load the BUILD file and run it with the above defined custom functions
exec(r.text)

Path("llvm-project/llvm/BUILD").write_text(output)

# Generate MLIR build definition
#
# Instead of going the LLVM route of only listing the static libraries,
# we must also copy over some files into build directories. Thus we load
# the Bazel BUILD file and render a new one from that.

r = requests.get(f"https://raw.githubusercontent.com/llvm/llvm-project/{llvm_commit}/utils/bazel/llvm-project-overlay/mlir/tblgen.bzl")
Path("llvm-project/mlir/tblgen.bzl").write_text(r.text)

output = """
load(":tblgen.bzl", "td_library")

exports_files([\"LICENSE.TXT\"])
"""
r = requests.get(f"https://raw.githubusercontent.com/llvm/llvm-project/{llvm_commit}/utils/bazel/llvm-project-overlay/mlir/BUILD.bazel")

MLIR_DIR = Path("llvm-project") / "mlir"
SYMBOL = "MLIR"
MLIR_LIBS = []
MLIR_TARGETS = []
MLIR_DELAYED_TARGETS = []

mlir_libs = libdir.glob("libMLIR*.a")
for lib in mlir_libs:
    basename = lib.name[7:-2]
    MLIR_LIBS.append(basename)

def empty(*args, **kwargs):
    pass

def cc_library(name, deps=None, *args, **kwargs):
    global output
    if deps is None:
        deps = []
    MLIR_TARGETS.append(name)
    # Remove third-party dependencies
    filtered_deps = [dep for dep in deps if (not dep.startswith("@llvm_"))]
    output += f"""
cc_library(
    name = "{name}",
    linkopts = {make_linkopts(name)},
    visibility = ["//visibility:public"],
    deps = {filtered_deps},
)"""

def make_linkopts(name):
    # TODO: More strategies
    #   1. If the lib doesn't exist, try to find a more global, e.g. QuantOps -> Quant
    #   2. Otherwise, add all MLIR libs and trust --as-needed linkage
    if name == "Support":
        return [f"-lMLIR{l}" for l in MLIR_LIBS]
    if name == "Analysis":
        return ["-lMLIRPresburger", "-lMLIRAnalysis", "-lMLIRLoopAnalysis"]
    if name == "CallOpInterfaces":
        return ["-lMLIRCallInterfaces"]
    libname = f"libMLIR{name}.a"
    upper_match = re.search("(.*)([A-Z][a-z]*)$", name)
    if (PREFIX / "lib" / libname).exists():
        return [f"-lMLIR{name}"] + [f"-lMLIR{l}" for l in MLIR_LIBS if l.startswith(name)]
    elif (PREFIX / "lib" / libname.replace("Dialect", "IR")).exists():
        return [f"-lMLIR{name.replace('Dialect', 'IR')}"]
    elif upper_match is not None:
        name = upper_match.group(1)
        if len(name) > 1:
            return make_linkopts(name)
    return []

def cc_headers_only(name, *args, **kwargs):
    global output
    output += f"""
cc_library(
    name = "{name}",
    visibility = ["//visibility:public"],
)"""


def alias(name, actual):
    global output
    output += f"""
alias(
    name = "{name}",
    actual = "{actual}",
    visibility = ["//visibility:public"],
)"""

def cc_binary(name, *args, **kwargs):
    global output
    output += f"""
genrule(
    name = "ln{name}",
    outs = ["{name}.bin"],
    cmd = "ln -s $$(which {name}) $@",
)

sh_binary(
    name = "{name}",
    srcs = ["{name}.bin"],
    visibility = ["//visibility:public"],
)
"""

def td_library(**kwargs):
    cc_name = kwargs["name"].replace("TdFiles", "")
    cc_deps = [dep.replace("TdFiles", "") for dep in kwargs.get("deps", [])]
    MLIR_DELAYED_TARGETS.append((cc_name, cc_deps))
    global output
    output += "\ntd_library(\n"
    for f in kwargs["srcs"]:
        import_file(f)
    for key, value in kwargs.items():
        if isinstance(value, str):
            output += f"    {key} = \"{value}\",\n"
        else:
            output += f"    {key} = {value},\n"
    output += "    visibility = [\"//visibility:public\"],\n"
    output += ")\n"

def gentbl_cc_library(name, td_file, **kwargs):
    global output
    #cc_deps = [dep.replace("TdFiles", "") for dep in kwargs.get("deps", [])]
    try:
        import_file(td_file)
    except:
        # Maybe remove everything that ends in "Files"?
        kwargs["deps"] = None
        return cc_library(name, **kwargs)
    output += f"""
filegroup(
   name = "{name}_filegroup",
   srcs = ["{td_file}"],
)

cc_library(
    name = "{name}",
    linkopts = {make_linkopts(name)},
    visibility = ["//visibility:public"],
    textual_hdrs = [":{name}_filegroup"],
)"""

# TODO: Customize for CUDA builds if necessary
def if_cuda_available(*args, **kwargs):
    return []

package = load = filegroup = empty
genlinalg = cc_library
# TODO: CAPI
mlir_c_api_cc_library = cc_library

# Load the BUILD file and run it with the above defined custom functions
exec(r.text)

for target in MLIR_DELAYED_TARGETS:
    if target[0] not in MLIR_TARGETS:
        cc_library(name=target[0], deps=target[1])

Path("llvm-project/mlir/BUILD").write_text(output)

