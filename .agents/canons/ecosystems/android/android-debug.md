---
activation: model_decision
description: Android debugging, Logcat triage, ANR/strict-mode diagnostics, and lightweight AVD workflows.
---

# Android Debugging & Diagnostics (`android-debug`)

## 1. Deterministic Triage Pipeline
1. **Compile & Lint Gate**: Run `./gradlew compileDebugKotlin lintDebug` to isolate static type and resource mismatches first.
2. **Unit & Robolectric Isolation**: Reproduce state/domain crashes via `./gradlew testDebugUnitTest` before booting an emulator.
3. **Lightweight AVD & Logcat**: Follow `avd-lightweight.md` for headless/low-RAM emulator flags and filtered `adb logcat` crash extraction.
