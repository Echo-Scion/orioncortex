---
activation: model_decision
description: Android unit, coroutine, Room DAO, and Jetpack Compose 6-Family UI state testing standards.
---

# Android Testing Standards (`android-tests`)

## 1. Real Contract Testing Over Synthetic Mocks
- **Domain & ViewModel**: Use `kotlinx-coroutines-test` (`runTest`, `StandardTestDispatcher`) with fake/in-memory repositories implementing real domain interfaces.
- **Persistence**: Test Room DAOs and migrations against real in-memory SQLite (`Room.inMemoryDatabaseBuilder`).
- **6-Family Compose UI Tests**: Verify `Loading`, `FirstTimeEmpty`, `FilteredEmpty`, `Populated`, `Error` retry callback, and Long-Text Gremlin truncation via `createComposeRule()`.
