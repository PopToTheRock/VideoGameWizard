# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

This is an Android project built with Gradle. Use Android Studio or the Gradle wrapper:

```bash
# Build debug APK
./gradlew assembleDebug

# Install on connected device/emulator
./gradlew installDebug

# Run all instrumented (UI) tests on connected device
./gradlew connectedAndroidTest

# Run a single instrumented test class
./gradlew connectedAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.videogamewizard.NavigationTest

# Run unit tests (currently none exist)
./gradlew test
```

## Architecture

The app is a single-module Android project (`app`) using **Jetpack Compose** and **Navigation Compose**.

All application code lives in `MainActivity.kt` — there are currently no separate files for screens, ViewModels, or data layers. The structure within that file:

- **`AppNavGraph`** — Navigation host with two routes: `"welcome"` → `WelcomeScreen`, `"home"` → `HomeScreen`
- **`WelcomeScreen`** — Landing screen with a "Get Started" button that navigates to home
- **`HomeScreen`** — Chat UI with a `LazyColumn` of `ChatMessage` items, a `UserChatFieldComposer` input row, and a typing indicator. AI replies are currently stubbed with a hardcoded response after a 600ms delay (no real AI integration yet)
- **`ChatMessage`** / **`ChatAuthor`** — local data model (enum + data class) private to the file

**Theme:** `ui/theme/` contains `Color.kt`, `Theme.kt`, `Type.kt`. The theme (`VideoGameWizardTheme`) uses Material3 with dynamic color on Android 12+ and falls back to a purple-based static palette.

**Tests:** Instrumented UI tests only, in `NavigationTest.kt`, using Compose test rules and `TestNavHostController`. Tests use `testTag` semantics (`"welcome_screen"`, `"home_screen"`) for node lookup.

## Key Dependencies

- Kotlin + Compose BOM
- `androidx.navigation.compose` for navigation
- `androidx.compose.material.icons.extended` for icons
- `minSdk = 24`, `targetSdk = 36`, Java 21

## Must Have Goals

- Engineering at the level of the best Google engineers in the world
- Ensuring best practices of all relevant programming languages, frameworks and third party software for this app
- Always evaluate any decisions made against what a top level Google engineer would do
