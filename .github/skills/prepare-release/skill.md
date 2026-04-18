---
name: prepare-release
description: Prepare a firmware release — version bump, compile matrix, binary size report, changelog, and flashing instructions.
---

# Prepare Release

## When to Use
When preparing a versioned release of a firmware project for distribution, deployment, or archival.

## Steps

### 1. Version Bump
- Determine the version increment: major (breaking), minor (feature), patch (fix).
- Update version in:
  - Main sketch or `version.h` header
  - `platformio.ini` or build config (if versioned)
  - `library.json` or `library.properties` (if publishing a library)
- Use semantic versioning: `MAJOR.MINOR.PATCH`.

### 2. Compile Matrix
Run `scripts/build-all.sh` (or equivalent) to compile for every supported board:
- Record pass/fail for each board target.
- Fix any compile failures before proceeding.
- Verify that all example sketches also compile.

### 3. Binary Size Report
For each board target, record:

| Board | Flash Used | Flash Total | RAM Used | RAM Total | Delta vs Previous |
|-------|-----------|-------------|---------|-----------|-------------------|
| ... | ... | ... | ... | ... | ... |

- Flag any significant size increases (>5% flash or >10% RAM) for review.
- Use `xtensa-esp32-elf-size` or PlatformIO's size output.

### 4. Run Tests
- Run all host-side unit tests: `pio test -e native` or equivalent.
- Verify all tests pass.
- Run on-device smoke tests if hardware is available.
- Note any skipped tests and why.

### 5. Verify Simulation Regressions
- Check `test/simulations/` for any simulations affected by changes in this release.
- Re-run affected simulations and compare results against previous baselines.
- If simulation results differ, document the change in the changelog.
- Verify `test/simulations/EXPERIMENT_LOG.md` is up to date.

### 6. Generate Changelog
Following Keep a Changelog format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Removed
- ...
```

- Reference issue/PR numbers where applicable.
- Include binary size impact for significant changes.

### 6. Build Release Binaries
- Build optimized binaries for each supported board.
- Name format: `<project>-<version>-<board>.bin`
- Store in `releases/` or as artifacts.
- Generate SHA256 checksums: `sha256sum *.bin > checksums.txt`

### 7. Write Flash Instructions
For each board, document:
- Required tool: `esptool.py`, Arduino IDE, PlatformIO CLI
- Flash command with exact parameters:
  ```bash
  esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 921600 \
    write_flash -z 0x0 firmware.bin
  ```
- Boot mode entry procedure (hold BOOT, press EN, release BOOT)
- Post-flash verification steps
- Required partition table (if custom)

### 8. Update Documentation
- Update README with new version number and features.
- Update wiring docs if hardware connections changed.
- Update API docs if interfaces changed.
- Tag the release in git: `git tag -a vX.Y.Z -m "Release X.Y.Z"`

## Release Checklist

- [ ] Version bumped in all locations
- [ ] All board targets compile
- [ ] All examples compile
- [ ] Host tests pass
- [ ] Simulation regressions verified (affected simulations re-run)
- [ ] Smoke tests pass (or documented as skipped)
- [ ] Changelog updated
- [ ] Binary size report generated
- [ ] Release binaries built and checksummed
- [ ] Flash instructions verified
- [ ] Documentation updated
- [ ] Git tag created

## Acceptance Criteria
- Every item in the release checklist is completed or explicitly noted as skipped with justification.
- No compile warnings for any board target.
- Binary size delta documented for reviewer.
