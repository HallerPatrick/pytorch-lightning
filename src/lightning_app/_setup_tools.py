#!/usr/bin/env python
# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import glob
import logging
import os
import re
import shutil
from typing import List

_PACKAGE_ROOT = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.dirname(_PACKAGE_ROOT)


def _load_requirements(path_dir: str, file_name: str = "requirements.txt", comment_char: str = "#") -> List[str]:
    """Load requirements from a file.

    >>> _load_requirements(_PROJECT_ROOT)  # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    [...]
    """
    with open(os.path.join(path_dir, file_name)) as file:
        lines = [ln.strip() for ln in file.readlines()]
    reqs = []
    for ln in lines:
        # filer all comments
        if comment_char in ln:
            ln = ln[: ln.index(comment_char)].strip()
        # skip directly installed dependencies
        if ln.startswith("http"):
            continue
        # skip index url
        if ln.startswith("--extra-index-url"):
            continue
        if ln:  # if requirement is not empty
            reqs.append(ln)
    return reqs


def _load_readme_description(path_dir: str, homepage: str, ver: str) -> str:
    """Load readme as decribtion."""
    path_readme = os.path.join(path_dir, "README.md")
    with open(path_readme, encoding="utf-8") as fp:
        text = fp.read()

    # https://github.com/PyTorchLightning/pytorch-lightning/raw/master/docs/source/_images/lightning_module/pt_to_pl.png
    github_source_url = os.path.join(homepage, "raw", ver)
    # replace relative repository path to absolute link to the release
    #  do not replace all "docs" as in the readme we reger some other sources with particular path to docs
    text = text.replace("docs/source/_static/", f"{os.path.join(github_source_url, 'docs/source/_static/')}")

    # readthedocs badge
    text = text.replace("badge/?version=stable", f"badge/?version={ver}")
    text = text.replace("lightning.readthedocs.io/en/stable/", f"lightning.readthedocs.io/en/{ver}")
    # codecov badge
    text = text.replace("/branch/master/graph/badge.svg", f"/release/{ver}/graph/badge.svg")
    # replace github badges for release ones
    text = text.replace("badge.svg?branch=master&event=push", f"badge.svg?tag={ver}")

    skip_begin = r"<!-- following section will be skipped from PyPI description -->"
    skip_end = r"<!-- end skipping PyPI description -->"
    # todo: wrap content as commented description
    text = re.sub(rf"{skip_begin}.+?{skip_end}", "<!--  -->", text, flags=re.IGNORECASE + re.DOTALL)

    # # https://github.com/Borda/pytorch-lightning/releases/download/1.1.0a6/codecov_badge.png
    # github_release_url = os.path.join(homepage, "releases", "download", ver)
    # # download badge and replace url with local file
    # text = _parse_for_badge(text, github_release_url)
    return text


def _create_meta_package(package_dir: str = _PACKAGE_ROOT, folder: str = _PROJECT_ROOT, new_pkg: str = "lightning.app"):
    """
    >>> _create_meta_package()
    """
    KEEP_FILES = ("_logger", "_root_logger", "_console", "formatter", "_PACKAGE_ROOT", "_PROJECT_ROOT")
    pkg_name = os.path.basename(package_dir)
    py_files = glob.glob(os.path.join(package_dir, "**", "*.py"), recursive=True)
    for py_file in py_files:
        local_path = py_file.replace(package_dir + os.path.sep, "")
        fname = os.path.basename(py_file)
        if "-" in fname:
            continue

        if fname in ("__init__.py", "__main__.py"):
            with open(py_file) as fp:
                lines = fp.readlines()
            body = []
            # ToDo: consider some more aggressive pruning
            for i, ln in enumerate(lines):
                ln = ln[: ln.index("#")] if "#" in ln else ln
                ln = ln.rstrip()
                var = re.match(r"^([\w+_]+) =", ln)
                if var:
                    name = var.groups()[0]
                    if name not in KEEP_FILES:
                        continue
                    if name.startswith("__") and name != "__all__":
                        continue
                    dirs = [d for d in os.path.dirname(local_path).split(os.path.sep) if d]
                    import_path = ".".join([pkg_name] + dirs)
                    body.append(f"from {import_path} import {name}  # noqa: F401")
                elif "import " in ln and "-" in ln:
                    continue
                elif "__about__" not in ln:
                    body.append(ln.replace(pkg_name, new_pkg))
        else:
            if fname.startswith("_") and fname not in ("__main__.py",):
                logging.warning(f"unsupported file: {local_path}")
                continue
            # ToDO: perform some smarter parsing - preserve Constants, lambdas, etc
            # spec = spec_from_file_location(os.path.join(pkg_name, local_path), py_file)
            # py = module_from_spec(spec)
            # spec.loader.exec_module(py)
            with open(py_file) as fp:
                lines = fp.readlines()
            body = []
            skip_offset = 0
            for i, ln in enumerate(lines):
                ln = ln[: ln.index("#")] if "#" in ln else ln
                ln = ln.rstrip()
                if skip_offset and ln:
                    offset = len(ln) - len(ln.lstrip())
                    if offset >= skip_offset:
                        continue
                    skip_offset = offset
                import_path = pkg_name + "." + local_path.replace(".py", "").replace(os.path.sep, ".")
                if "-" in import_path:
                    continue
                var = re.match(r"^([\w+_]+) =", ln)
                if var:

                    name = var.groups()[0]
                    if name not in KEEP_FILES:
                        continue
                    body.append(f"from {import_path} import {name}  # noqa: F401")
                if "import " in ln and "-" in ln:
                    continue
                if any(ln.lstrip().startswith(k) for k in ["def", "class"]):
                    name = ln.replace("def ", "").replace("class ", "").strip()
                    if "on_before_run" in name:
                        # fixme
                        continue
                    idx = [name.index(s) if s in name else len(name) for s in "():"]
                    name = name[: min(idx)]
                    # skip private, TODO: consider skip even protected
                    if name.startswith("__") or "=" in name:
                        continue
                    body.append(f"from {import_path} import {name}  # noqa: F401")
                    skip_offset = len(ln) - len(ln.lstrip()) + 4

        new_file = os.path.join(folder, new_pkg.replace(".", os.path.sep), local_path)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        with open(new_file, "w") as fp:
            fp.writelines([ln + os.linesep for ln in body])

        py_files = glob.glob(os.path.join(folder, new_pkg.replace(".", os.path.sep), "*.py"))
        for py_file in py_files:
            fname = os.path.basename(py_file)
            if fname not in ("__init__.py", "__main__.py"):
                continue
            shutil.copy(py_file, os.path.join(folder, new_pkg.split(".")[0], fname))
