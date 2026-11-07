---
activation: model_decision
description: Android Jetpack Compose UI patterns, Material 3 tokens, concentric geometry, and 8pt spatial grid.
---

# Android UI Patterns (`android-ui-patterns`)

## 1. Task-First Layout & Concentric Geometry
- Select layout by primary user task (`LazyColumn` Action List, Adaptive `SupportingPaneScaffold` Split-View, or Data Table).
- Enforce concentric corner radii (`outerRadius = innerRadius + padding`, e.g., `RoundedCornerShape(16.dp)` card with `8.dp` padding and `RoundedCornerShape(8.dp)` inner child).
- Enforce the 8dp spatial grid (`4.dp`, `8.dp`, `12.dp`, `16.dp`, `24.dp`, `32.dp`) and minimum `48.dp` touch targets.
- See `ui-compose.md` and `ui-xml-views.md` for detailed Compose `@Preview` and XML layout interoperability rules.
