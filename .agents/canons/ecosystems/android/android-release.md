---
activation: model_decision
description: Android release hardening, R8/ProGuard shrinking, versionCode/versionName synchronization, and signing verification.
---

# Android Release Pipeline (`android-release`)

## 1. Pre-Release Checklist
1. **SemVer & Manifest Sync**: Run `python .agents/scripts/orion.py dna semver` to synchronize `versionName` and increment `versionCode` in `build.gradle` / `build.gradle.kts`.
2. **R8 & Consumer Rules**: Verify `isMinifyEnabled = true` and `isShrinkResources = true` on release builds with explicit `@Serializable` / Retrofit keep rules.
3. **Verification Gates**: Ensure `./gradlew testDebugUnitTest lintRelease` and `python .agents/scripts/orion.py push` pass with Exit Code 0.
