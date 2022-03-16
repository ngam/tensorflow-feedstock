from glob import glob as py_glob
from pathlib import Path
from shutil import copyfile
from subprocess import check_output
import os
import re
import requests


# TODO: Automatically extract this
llvm_commit = "55c71c9eac9bc7f956a05fa9258fad4f86565450"
Path("llvm-project/llvm").mkdir(exist_ok=True, parents=True)
Path("llvm-project/mlir").mkdir(exist_ok=True, parents=True)

# Compute dependencies between LLVM/MLIR static libraries
#
# LIEF doesn't yet support static libraries: https://github.com/lief-project/LIEF/issues/233
# Thus this is a small parser around the output of `nm`.

libs = list((Path(os.environ["PREFIX"]) / "lib").glob("libMLIR*.a")) + list(
    (Path(os.environ["PREFIX"]) / "lib").glob("libLLVM*.a")
)
lookup = {}
deps = {}

# Parse the output of nm
for lib in libs:
    deps[lib.name] = set()
    lookup[lib.name] = {
        "defined": set(),
        "undefined": set()
    }
    out = check_output([os.environ["NM"], lib]).decode()
    lines = out.split("\n")[1:]
    for line in lines:
        if line.startswith(str(lib)) or line.endswith(":"):
            continue
        split = line.split()
        if len(split) == 0:
            continue
        state = split[-2].lower()
        symbol = split[-1]
        if state in ('b', 't', 'd'):
            lookup[lib.name]["defined"].add(symbol)
        elif state == "u":
            lookup[lib.name]["undefined"].add(symbol)

# Resolve undefined symbols
for lib in libs:
    for possible_lib in libs:
        if len(lookup[lib.name]["undefined"]) == 0:
            break
        undefined_len = len(lookup[lib.name]["undefined"])
        lookup[lib.name]["undefined"] -=  lookup[possible_lib.name]["defined"]
        if len(lookup[lib.name]["undefined"]) < undefined_len:
            deps[lib.name].add(possible_lib.name)

# Resolve transitive dependencies; by using this approach we also can handle
# cyclic dependencies between libraries.
deps_changed = True
while deps_changed:
    deps_changed = False
    for lib in libs:
        dep_len = len(deps[lib.name])
        for dep in list(deps[lib.name]):
            deps[lib.name] |= deps[dep]
        if len(deps[lib.name]) != dep_len:
            deps_changed = True

# The casing in the bazel files is different than the actual libs, so look it up here.
case_lookup = {}
for lib in deps.keys():
    case_lookup[lib[3:-2].lower()] = lib[3:-2]

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
    cwd = os.getcwd()
    os.chdir(os.environ["PREFIX"])
    for a in search:
        out += py_glob(a)
    os.chdir(cwd)
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

def add_link_dependencies(libraries):
    """Add static library dependencies to the link_opts."""
    link_opts = []
    for lib in libraries:
        link_opts.append(f"-l{lib}")
        dependencies = deps[f"lib{lib}.a"]
        for dep in dependencies:
            name = dep[3:-2]
            link = f"-l{name}"
            if link not in link_opts:
                link_opts.append(link)

    return link_opts

def make_linkopts(name):
    fullname = SYMBOL + name
    # Fix the caseing of the library to match the actual file names.
    if fullname.lower() in case_lookup:
        fullname = case_lookup[fullname.lower()]

    # There are some difference in the names used in Bazel and the actual static libraries.
    # This lookup here is by done by simply guessing them given
    # the linkage errors that popped up.
    if fullname == "MLIRAnalysis":
        return add_link_dependencies(["MLIRPresburger", "MLIRAnalysis", "MLIRLoopAnalysis"])
    if fullname == "MLIRCallOpInterfaces":
        return add_link_dependencies(["MLIRCallInterfaces"])
    if fullname == "MLIRShapeTransforms":
        return add_link_dependencies(["MLIRShape", "MLIRShapeOpsTransforms"])

    libname = f"lib{fullname}.a"
    upper_match = re.search("(.*)([A-Z][a-z]*)$", name)
    if (PREFIX / "lib" / libname).exists():
        return add_link_dependencies([f"{fullname}"])
    elif (PREFIX / "lib" / libname.replace("Dialect", "IR")).exists():
        return [f"-l{fullname.replace('Dialect', 'IR')}"]
    elif upper_match is not None:
        name = upper_match.group(1)
        if len(name) > 1:
            return make_linkopts(name)
    return []


libdir = Path(os.environ["PREFIX"]) / "lib"

output = """
exports_files([\"LICENSE.TXT\"])
"""

r = requests.get(f"https://raw.githubusercontent.com/llvm/llvm-project/{llvm_commit}/llvm/LICENSE.txt")
Path("llvm-project/llvm/LICENSE.TXT").write_text(r.text)

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
r = requests.get(f"https://raw.githubusercontent.com/llvm/llvm-project/{llvm_commit}/mlir/LICENSE.txt")
Path("llvm-project/mlir/LICENSE.TXT").write_text(r.text)

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

