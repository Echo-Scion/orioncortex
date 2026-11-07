---
activation: model_decision
description: Native Android (Kotlin + Jetpack Compose) project initialization, Gradle Version Catalogs, and 5-Tier DNA layout.
---

# Android Ecosystem Initialization (`android-init`)

## 1. Canonical Directory & 5-Tier DNA Layout
Structure new Android modules cleanly across the 5-Tier Orbital Strata:
- `1_contracts`: `core/model/`, DTOs, Room `@Entity` definitions, and Kotlinx Serialization schemas.
- `2_domain`: `domain/usecase/`, pure Kotlin business rules, and repository interfaces (zero `android.*` imports).
- `3_services`: `data/repository/`, Room `@Dao`, Retrofit/Ktor clients, and DataStore persistence.
- `4_state`: `ui/<feature>/*ViewModel.kt`, immutable `*UiState` sealed interfaces, and `StateFlow` reducers.
- `5_presentation`: `ui/<feature>/*Screen.kt`, stateless `@Composable` views, and `@Preview` sidecars.

## 2. Gradle & Toolchain Baseline
- Use `gradle/libs.versions.toml` (Version Catalogs) for all dependency coordinates.
- Enable Kotlin Coroutines, `StateFlow`, Room with WAL mode, and Jetpack Compose Material 3.
