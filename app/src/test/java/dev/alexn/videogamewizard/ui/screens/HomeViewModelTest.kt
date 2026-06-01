package dev.alexn.videogamewizard.ui.screens

import dev.alexn.videogamewizard.MainDispatcherRule
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.network.ChatResponse
import dev.alexn.videogamewizard.data.repository.ChatRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException

@OptIn(ExperimentalCoroutinesApi::class)
class HomeViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    // ChatRepository is a final class; MockK can mock it directly.
    private val repository: ChatRepository = mockk()

    // Share runTest's scheduler with the Main dispatcher set by the rule, so
    // advanceUntilIdle() also drives coroutines launched on viewModelScope.
    private val scheduler get() = mainDispatcherRule.dispatcher.scheduler

    @Test
    fun `initial state has only the greeting message`() {
        val vm = HomeViewModel(repository)
        val state = vm.uiState.value

        assertEquals(1, state.messages.size)
        assertEquals(ChatAuthor.AI, state.messages[0].author)
        assertEquals("", state.input)
        assertFalse(state.isAiTyping)
    }

    @Test
    fun `onInputChange updates the input field`() {
        val vm = HomeViewModel(repository)
        vm.onInputChange("zelda tips")
        assertEquals("zelda tips", vm.uiState.value.input)
    }

    @Test
    fun `successful send appends user and AI messages and clears input`() = runTest(scheduler) {
        coEvery { repository.sendMessage(any(), any()) } returns
            Result.success(ChatResponse(response = "Use bombs on the rocks."))

        val vm = HomeViewModel(repository)
        vm.onInputChange("How do I beat the boss?")
        vm.sendMessage()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(3, state.messages.size) // greeting + user + ai
        assertEquals(ChatAuthor.USER, state.messages[1].author)
        assertEquals("How do I beat the boss?", state.messages[1].text)
        assertEquals(ChatAuthor.AI, state.messages[2].author)
        assertEquals("Use bombs on the rocks.", state.messages[2].text)
        assertFalse(state.isAiTyping)
        assertEquals("", state.input)
    }

    @Test
    fun `send trims whitespace before dispatching`() = runTest(scheduler) {
        val messageSlot = slot<String>()
        coEvery { repository.sendMessage(capture(messageSlot), any()) } returns
            Result.success(ChatResponse(response = "ok"))

        val vm = HomeViewModel(repository)
        vm.onInputChange("   spaced out   ")
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals("spaced out", messageSlot.captured)
        assertEquals("spaced out", vm.uiState.value.messages[1].text)
    }

    @Test
    fun `send passes prior messages as history excluding the new message`() = runTest(scheduler) {
        val historySlot = slot<List<ChatMessage>>()
        coEvery { repository.sendMessage(any(), capture(historySlot)) } returns
            Result.success(ChatResponse(response = "ok"))

        val vm = HomeViewModel(repository)
        vm.onInputChange("first question")
        vm.sendMessage()
        advanceUntilIdle()

        // Only the seeded greeting precedes the new user message.
        assertEquals(1, historySlot.captured.size)
        assertEquals(ChatAuthor.AI, historySlot.captured[0].author)
    }

    @Test
    fun `blank input is rejected and nothing is sent`() = runTest(scheduler) {
        val vm = HomeViewModel(repository)
        vm.onInputChange("    ")
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals(1, vm.uiState.value.messages.size)
        coVerify(exactly = 0) { repository.sendMessage(any(), any()) }
    }

    @Test
    fun `oversized input is rejected and nothing is sent`() = runTest(scheduler) {
        val vm = HomeViewModel(repository)
        vm.onInputChange("a".repeat(4097)) // MAX_INPUT_LENGTH is 4096
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals(1, vm.uiState.value.messages.size)
        coVerify(exactly = 0) { repository.sendMessage(any(), any()) }
    }

    @Test
    fun `a second send is ignored while a request is in flight`() = runTest(scheduler) {
        coEvery { repository.sendMessage(any(), any()) } returns
            Result.success(ChatResponse(response = "ok"))

        val vm = HomeViewModel(repository)
        vm.onInputChange("first")
        vm.sendMessage()
        // StandardTestDispatcher queues the coroutine, so the in-flight guard
        // is observable before the scheduler is advanced.
        assertTrue(vm.uiState.value.isAiTyping)

        vm.onInputChange("second")
        vm.sendMessage() // should be ignored: isAiTyping == true
        advanceUntilIdle()

        coVerify(exactly = 1) { repository.sendMessage(any(), any()) }
        val messages = vm.uiState.value.messages
        assertEquals(3, messages.size) // greeting + first + ai, never "second"
        assertEquals("first", messages[1].text)
    }

    @Test
    fun `timeout failure shows the timeout error message`() = runTest(scheduler) {
        assertErrorMessage(
            failure = SocketTimeoutException(),
            expected = "Request timed out. The server may be busy — try again.",
        )
    }

    @Test
    fun `connection failure shows the unreachable-server message`() = runTest(scheduler) {
        assertErrorMessage(
            failure = ConnectException(),
            expected = "Couldn't reach the server. Make sure it's running on your PC.",
        )
    }

    @Test
    fun `generic IO failure shows the unreachable-server message`() = runTest(scheduler) {
        assertErrorMessage(
            failure = IOException(),
            expected = "Couldn't reach the server. Make sure it's running on your PC.",
        )
    }

    @Test
    fun `unexpected failure shows the generic error message`() = runTest(scheduler) {
        assertErrorMessage(
            failure = RuntimeException("boom"),
            expected = "Something went wrong. Please try again.",
        )
    }

    @Test
    fun `clearChat resets to a single cleared-chat message`() {
        val vm = HomeViewModel(repository)
        vm.clearChat()

        val state = vm.uiState.value
        assertEquals(1, state.messages.size)
        assertEquals(ChatAuthor.AI, state.messages[0].author)
        assertEquals("Chat cleared. What do you want help with?", state.messages[0].text)
        assertFalse(state.isAiTyping)
    }

    @Test
    fun `message ids are unique across a conversation`() = runTest(scheduler) {
        coEvery { repository.sendMessage(any(), any()) } returns
            Result.success(ChatResponse(response = "ok"))

        val vm = HomeViewModel(repository)
        vm.onInputChange("q")
        vm.sendMessage()
        advanceUntilIdle()

        val ids = vm.uiState.value.messages.map { it.id }
        assertEquals(ids.size, ids.distinct().size)
    }

    /** Sends a message whose repository call fails and asserts the rendered AI error text. */
    private fun TestScope.assertErrorMessage(failure: Throwable, expected: String) {
        coEvery { repository.sendMessage(any(), any()) } returns Result.failure(failure)

        val vm = HomeViewModel(repository)
        vm.onInputChange("anything")
        vm.sendMessage()
        advanceUntilIdle()

        val last = vm.uiState.value.messages.last()
        assertEquals(ChatAuthor.AI, last.author)
        assertEquals(expected, last.text)
        assertFalse(vm.uiState.value.isAiTyping)
    }
}
