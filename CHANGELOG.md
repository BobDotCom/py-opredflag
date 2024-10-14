# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No changes yet.

## [0.3.0] - 2024-10-14

### Added

- Added official support for python 3.12

### Changed

- Changed Aiohttp request timeout from 30s to default (5m)

## [0.2.0] - 2023-10-24

### Added

- Added full Semver support, including pre-releases and build metadata.
- Added new "none" value for version comparison, to indicate only other pre-release
  versions of the same patch are compatible.

## [0.1.0] - 2023-09-30

### Added

- Added request caching, resulting in major performance improvements when multi-keys are
  used.

### Changed

- Replaced `update_assets(...)` with `await Updater(...).run()`.
- `opredflag.updater` now uses asyncIO, resulting in major performance improvements.
- Reformatted output. Updates are printed to stdout, while non-changes are returned by
  the script.

### Fixed

- Files will not be updated if script fails.

## [0.0.2] - 2023-09-27

### Added

- Added support for python 3.10.

## [0.0.1] - 2023-09-27

### Changed

- Changed updater CLI command to `oprf update`.

## [0.0.1.alpha.2] - 2023-09-26

### Fixed

- Fixed documentation dependency conflicts.

## [0.0.1.alpha] - 2023-09-26

### Added

- Initial version.

[unreleased]: https://github.com/BobDotCom/py-opredflag/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.3.0
[0.2.0]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.2.0
[0.1.0]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.1.0
[0.0.2]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.0.2
[0.0.1]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.0.1
[0.0.1.alpha.2]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.0.1.alpha.2
[0.0.1.alpha]: https://github.com/BobDotCom/py-opredflag/releases/tag/v0.0.1.alpha
