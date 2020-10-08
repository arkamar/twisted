# -*- test-case-name: twisted.python.test.test_setup -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# pylint: disable=I0011,C0103,C9302,W9401,W9402

"""
Setuptools convenience functionality.

This file must not import anything from Twisted, as it is loaded by C{exec} in
C{setup.py}. If you need compatibility functions for this code, duplicate them
here.

@var _EXTRA_OPTIONS: These are the actual package names and versions that will
    be used by C{extras_require}.  This is not passed to setup directly so that
    combinations of the packages can be created without the need to copy
    package names multiple times.

@var _EXTRAS_REQUIRE: C{extras_require} is a dictionary of items that can be
    passed to setup.py to install optional dependencies.  For example, to
    install the optional dev dependencies one would type::

        pip install -e ".[dev]"

    This has been supported by setuptools since 0.5a4.

@var _PLATFORM_INDEPENDENT: A list of all optional cross-platform dependencies,
    as setuptools version specifiers, used to populate L{_EXTRAS_REQUIRE}.

@var _EXTENSIONS: The list of L{ConditionalExtension} used by the setup
    process.

@var notPortedModules: Modules that are not yet ported to Python 3.
"""

import io
import os
import platform
import re
import sys
from typing import Any, Dict, List, cast

from distutils.command import build_ext
from distutils.errors import CompileError
from setuptools import Extension, find_packages


STATIC_PACKAGE_METADATA = dict(
    name="Twisted",
    description="An asynchronous networking framework written in Python",
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Glyph Lefkowitz",
    maintainer_email="glyph@twistedmatrix.com",
    url="https://twistedmatrix.com/",
    project_urls={
        "Documentation": "https://twistedmatrix.com/documents/current/",
        "Source": "https://github.com/twisted/twisted",
        "Issues": "https://twistedmatrix.com/trac/report",
    },
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    python_requires=">=3.5",
    long_description_content_type="text/x-rst",
    install_requires=[
        "zope.interface >= 4.4.2",
        "constantly >= 15.1",
        "incremental >= 16.10.1",
        "Automat >= 0.8.0",
        "hyperlink >= 17.1.1",
        "PyHamcrest >= 1.9.0",
        "attrs >= 19.2.0",
    ],
    use_incremental=True,
    setup_requires=["incremental >= 16.10.1"],
    include_package_data=True,
    exclude_package_data={
        "": ["*.c", "*.h", "*.pxi", "*.pyx", "build.bat"],
    },
    zip_safe=False,
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "ckeygen = twisted.conch.scripts.ckeygen:run",
            "cftp = twisted.conch.scripts.cftp:run",
            "conch = twisted.conch.scripts.conch:run",
            "mailmail = twisted.mail.scripts.mailmail:run",
            "pyhtmlizer = twisted.scripts.htmlizer:run",
            "tkconch = twisted.conch.scripts.tkconch:run",
            "trial = twisted.scripts.trial:run",
            "twist = twisted.application.twist._twist:Twist.main",
            "twistd = twisted.scripts.twistd:run",
        ],
    },
)  # type: Dict[str, Any]


_dev = [
    "pyflakes >= 1.0.0",
    "twisted-dev-tools >= 0.0.2",
    "python-subunit",
    "towncrier >= 17.4.0",
    "twistedchecker >= 0.7.2",
    # force upgrades for rtd default packages: https://git.io/JU73V
    "alabaster~=0.7.12",
    "commonmark~=0.9.1",
    "docutils~=0.16.0",
    "mock~=4.0",
    "pillow~=7.2",
    "readthedocs-sphinx-ext~=2.1",
    "recommonmark~=0.6.0",
    "sphinx~=3.2",
    "sphinx-rtd-theme~=0.5.0",
]

_EXTRA_OPTIONS = dict(
    dev=_dev,
    tls=[
        "pyopenssl >= 16.0.0",
        # service_identity 18.1.0 added support for validating IP addresses in
        # certificate subjectAltNames
        "service_identity >= 18.1.0",
        "idna >= 2.4",
    ],
    conch=[
        "pyasn1",
        "cryptography >= 2.6",
        "appdirs >= 1.4.0",
        "bcrypt >= 3.0.0",
    ],
    serial=["pyserial >= 3.0", 'pywin32 != 226; platform_system == "Windows"'],
    macos=["pyobjc-core", "pyobjc-framework-CFNetwork", "pyobjc-framework-Cocoa"],
    windows=["pywin32 != 226"],
    http2=["h2 >= 3.0, < 4.0", "priority >= 1.1.0, < 2.0"],
    contextvars=['contextvars >= 2.4, < 3; python_version < "3.7"'],
)

_PLATFORM_INDEPENDENT = (
    _EXTRA_OPTIONS["tls"]
    + _EXTRA_OPTIONS["conch"]
    + _EXTRA_OPTIONS["serial"]
    + _EXTRA_OPTIONS["http2"]
    + _EXTRA_OPTIONS["contextvars"]
)

_EXTRAS_REQUIRE = {
    "dev": _EXTRA_OPTIONS["dev"],
    "tls": _EXTRA_OPTIONS["tls"],
    "conch": _EXTRA_OPTIONS["conch"],
    "serial": _EXTRA_OPTIONS["serial"],
    "http2": _EXTRA_OPTIONS["http2"],
    "contextvars": _EXTRA_OPTIONS["contextvars"],
    "all_non_platform": _PLATFORM_INDEPENDENT,
    "macos_platform": (_EXTRA_OPTIONS["macos"] + _PLATFORM_INDEPENDENT),
    "windows_platform": (_EXTRA_OPTIONS["windows"] + _PLATFORM_INDEPENDENT),
}
_EXTRAS_REQUIRE["osx_platform"] = _EXTRAS_REQUIRE["macos_platform"]


class ConditionalExtension(Extension):
    """
    An extension module that will only be compiled if certain conditions are
    met.

    @param condition: A callable of one argument which returns True or False to
        indicate whether the extension should be built. The argument is an
        instance of L{build_ext_twisted}, which has useful methods for checking
        things about the platform.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.condition = kwargs.pop("condition", lambda builder: True)
        Extension.__init__(self, *args, **kwargs)


# The C extensions used for Twisted.
_EXTENSIONS = [
    ConditionalExtension(
        "twisted.test.raiser",
        sources=["src/twisted/test/raiser.c"],
        condition=lambda _: _isCPython,
    ),
    ConditionalExtension(
        "twisted.internet.iocpreactor.iocpsupport",
        sources=[
            "src/twisted/internet/iocpreactor/iocpsupport/iocpsupport.c",
            "src/twisted/internet/iocpreactor/iocpsupport/winsock_pointers.c",
        ],
        libraries=["ws2_32"],
        condition=lambda _: _isCPython and sys.platform == "win32",
    ),
]


def _longDescriptionFromReadme(readme: str) -> str:
    """
    Generate a PyPI long description from the readme.

    @param readme: Path to the readme reStructuredText file.

    @return: Keyword arguments to be passed to C{setuptools.setup()}.
    """
    with io.open(readme, encoding="utf-8") as f:
        readmeRst = f.read()

    # Munge links of the form `NEWS <NEWS.rst>`_ to point at the appropriate
    # location on GitHub so that they function when the long description is
    # displayed on PyPI.
    return re.sub(
        r"`([^`]+)\s+<(?!https?://)([^>]+)>`_",
        r"`\1 <https://github.com/twisted/twisted/blob/trunk/\2>`_",
        readmeRst,
        flags=re.I,
    )


def getSetupArgs(
    extensions: List[ConditionalExtension] = _EXTENSIONS,
    readme: str = "README.rst",
) -> Dict[str, Any]:
    """
    Generate arguments for C{setuptools.setup()}

    @param extensions: C extension modules to maybe build. This argument is to
        be used for testing.
    @param readme: Path to the readme reStructuredText file. This argument is
        to be used for testing.

    @return: The keyword arguments to be used by the setup method.
    """

    # Use custome class to build the extensions.
    class my_build_ext(build_ext_twisted):
        conditionalExtensions = extensions

    return {
        "packages": find_packages("src"),
        "long_description": _longDescriptionFromReadme(readme),
        # This is a workaround for distutils behavior; ext_modules isn't
        # actually used by our custom builder.  distutils deep-down checks
        # to see if there are any ext_modules defined before invoking
        # the build_ext command.  We need to trigger build_ext regardless
        # because it is the thing that does the conditional checks to see
        # if it should build any extensions.  The reason we have to delay
        # the conditional checks until then is that the compiler objects
        # are not yet set up when this code is executed.
        "ext_modules": extensions,
        "cmdclass": {"build_ext": my_build_ext},
        "extras_require": _EXTRAS_REQUIRE,
        **STATIC_PACKAGE_METADATA,
    }


# Helpers and distutil tweaks


class build_ext_twisted(build_ext.build_ext):  # type: ignore[name-defined]
    """
    Allow subclasses to easily detect and customize Extensions to
    build at install-time.
    """

    def prepare_extensions(self) -> None:
        """
        Prepare the C{self.extensions} attribute (used by
        L{build_ext.build_ext}) by checking which extensions in
        I{conditionalExtensions} should be built.  In addition, if we are
        building on NT, define the WIN32 macro to 1.
        """
        # always define WIN32 under Windows
        if os.name == "nt":
            self.define_macros = [("WIN32", 1)]
        else:
            self.define_macros = []

        # On Solaris 10, we need to define the _XOPEN_SOURCE and
        # _XOPEN_SOURCE_EXTENDED macros to build in order to gain access to
        # the msg_control, msg_controllen, and msg_flags members in
        # sendmsg.c. (according to
        # https://stackoverflow.com/questions/1034587).  See the documentation
        # of X/Open CAE in the standards(5) man page of Solaris.
        if sys.platform.startswith("sunos"):
            self.define_macros.append(("_XOPEN_SOURCE", 1))
            self.define_macros.append(("_XOPEN_SOURCE_EXTENDED", 1))

        self.extensions = [x for x in self.conditionalExtensions if x.condition(self)]

        for ext in self.extensions:
            ext.define_macros.extend(self.define_macros)

    def build_extensions(self) -> None:
        """
        Check to see which extension modules to build and then build them.
        """
        self.prepare_extensions()
        build_ext.build_ext.build_extensions(self)  # type: ignore[attr-defined]

    def _remove_conftest(self) -> None:
        for filename in ("conftest.c", "conftest.o", "conftest.obj"):
            try:
                os.unlink(filename)
            except EnvironmentError:
                pass

    def _compile_helper(self, content: str) -> bool:
        conftest = open("conftest.c", "w")
        try:
            with conftest:
                conftest.write(content)

            try:
                self.compiler.compile(["conftest.c"], output_dir="")
            except CompileError:
                return False
            return True
        finally:
            self._remove_conftest()

    def _check_header(self, header_name: str) -> bool:
        """
        Check if the given header can be included by trying to compile a file
        that contains only an #include line.
        """
        self.compiler.announce("checking for {} ...".format(header_name), 0)
        return self._compile_helper("#include <{}>\n".format(header_name))


def _checkCPython(platform: Any = platform) -> bool:
    """
    Checks if this implementation is CPython.

    This uses C{platform.python_implementation}.

    This takes C{sys} and C{platform} kwargs that by default use the real
    modules. You shouldn't care about these -- they are for testing purposes
    only.

    @return: C{False} if the implementation is definitely not CPython, C{True}
        otherwise.
    """
    return cast(bool, platform.python_implementation() == "CPython")


_isCPython = _checkCPython()  # type: bool

notPortedModules = [
    "twisted.mail.alias",
    "twisted.mail.bounce",
    "twisted.mail.mail",
    "twisted.mail.maildir",
    "twisted.mail.pb",
    "twisted.mail.relaymanager",
    "twisted.mail.scripts.__init__",
    "twisted.mail.tap",
    "twisted.mail.test.test_bounce",
    "twisted.mail.test.test_mail",
    "twisted.mail.test.test_options",
    "twisted.mail.test.test_scripts",
    "twisted.plugins.twisted_mail",
    "twisted.protocols.shoutcast",
    "twisted.web.soap",
    "twisted.web.test.test_soap",
]
