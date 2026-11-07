---
activation: model_decision
description: End-to-end Android Jetpack Compose feature recipe enforcing the 6-Family Screen State Machine and unidirectional state hoisting.
---

# Android Feature Recipe (`android-feature-recipe`)

## 1. Mandatory 6-Family Screen State Machine (`UiState`)
Every data-backed Android feature screen MUST model all 6 state families via a sealed interface:

```kotlin
sealed interface FeatureUiState {
    data object Loading : FeatureUiState
    data object FirstTimeEmpty : FeatureUiState
    data class FilteredEmpty(val query: String) : FeatureUiState
    data class Populated(val items: List<FeatureItem>, val isOfflineStale: Boolean = false) : FeatureUiState
    data class Error(val message: String, val retryActionLabel: String = "Retry") : FeatureUiState
}
```

## 2. Unidirectional State Hoisting & Gremlin Resilience
- **Stateful Route Composable**: Collects `viewModel.uiState.collectAsStateWithLifecycle()` and dispatches user intents.
- **Stateless Screen Composable**: Renders all 6 state families cleanly, enforcing `maxLines` + `TextOverflow.Ellipsis` to survive Long-Text Production Gremlins without layout overflow.
