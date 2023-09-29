.. currentmodule:: opredflag.updater

OPRF Asset Updater
==================

GitHub Action
-------------

The most common usage of this module is through the `OPRF Asset Updater <updater-action>`_
GitHub action. Documentation can be found in marketplace listing or the repository readme.

CLI Usage
---------

.. argparse::
    :module: opredflag.cli
    :func: get_parser
    :prog: oprf
    :path: update

Code Reference
--------------

.. autoclass:: Updater
    :members:

.. class:: Compatibility

    Represents a compatibility level between semantic versions.

    .. attribute:: MAJOR

        Compatibility with any major version, least strict.

    .. attribute:: MINOR

        Compatibility with any minor version with the same major version, less strict.

    .. attribute:: PATCH

        Compatibility with any patch version with the same major and minor version, most strict.
