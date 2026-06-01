package dev.alexn.videogamewizard

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.rules.TestWatcher
import org.junit.runner.Description

/**
 * JUnit rule that swaps `Dispatchers.Main` for a [TestDispatcher] for the
 * duration of each test, so coroutines launched on `viewModelScope` run on the
 * test scheduler and can be driven deterministically (`advanceUntilIdle`, etc.).
 *
 * Defaults to a [StandardTestDispatcher] (lazy): launched coroutines are queued
 * rather than executed eagerly, which lets tests observe intermediate state
 * (e.g. `isAiTyping == true`) before advancing the scheduler.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    val dispatcher: TestDispatcher = StandardTestDispatcher(),
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(dispatcher)
    }

    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
