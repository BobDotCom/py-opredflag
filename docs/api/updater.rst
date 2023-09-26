.. currentmodule:: opredflag.updater

OPRF Asset Updater
==================

GitHub Action
-------------

The most common usage of this module is through the `OPRF Asset Updater <updater-action>`_
GitHub action. Documentation can be found in marketplace listing or the repository readme.

CLI Usage
---------

.. code-block:: shell

    oprf updater --help


Code Reference
--------------

.. autofunction:: update_assets

.. class:: Compatibility

    Represents a compatibility level between semantic versions.

    .. attribute:: MAJOR

        Compatibility with any major version, least strict.

    .. attribute:: MINOR

        Compatibility with any minor version with the same major version, less strict.

    .. attribute:: PATCH

        Compatibility with any patch version with the same major and minor version, most strict.
