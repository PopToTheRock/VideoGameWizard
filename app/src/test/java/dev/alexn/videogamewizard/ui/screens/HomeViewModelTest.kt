package dev.alexn.videogamewizard.ui.screens

import dev.alexn.videogamewizard.MainDispatcherRule
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.repository.ChatHistoryRepository
import dev.alexn.videogamewizard.data.repository.ChatRepository
import dev.alexn.videogamewizard.data.repository.ChatStreamEvent
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import io.mockk.verify
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException

/** In-memory [ChatHistoryRepository] standing in for the Room-backed one. */
private class FakeChatHistoryRepository : ChatHistoryRepository {
    private val state = MutableStateFlow<List<ChatMessage>>(emptyList())
    private var nextId = 1L

    override val messages: Flow<List<ChatMessage>> = state

    override suspend fun append(author: ChatAuthor, text: String) {
        state.update { it + ChatMessage(id = nextId++, author = author, text = text) }
    }

    override suspend fun clear() {
        state.value = emptyList()
    }

    override suspend fun count(): Int = state.value.size
}

@OptIn(ExperimentalCoroutinesApi::class)
class HomeViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    // ChatRepository (network) is a final class; MockK can mock it directly.
    private val chatRepository: ChatRepository = mockk()
    private val historyRepository = FakeChatHistoryRepository()

    // Share runTest's scheduler with the Main dispatcher set by the rule.
    private val scheduler get() = mainDispatcherRule.dispatcher.scheduler

    /** Stubs the stream to emit [reply] as a single token, then complete (`done`). */
    private fun stubReply(reply: String) {
        every { chatRepository.streamMessage(any(), any()) } returns
            flowOf(ChatStreamEvent.Token(reply))
    }

    /** Builds the VM and lets `init` seed the greeting + the stateIn flow settle. */
    private fun TestScope.newViewModel(): HomeViewModel {
        val vm = HomeViewModel(chatRepository, historyRepository)
        advanceUntilIdle()
        return vm
    }

    @Test
    fun `initial state seeds a single greeting message`() = runTest(scheduler) {
        val state = newViewModel().uiState.value
        assertEquals(1, state.messages.size)
        assertEquals(ChatAuthor.AI, state.messages[0].author)
        assertEquals("", state.input)
        assertFalse(state.isResponding)
        assertNull(state.streamingText)
    }

    @Test
    fun `onInputChange updates the input field`() = runTest(scheduler) {
        val vm = newViewModel()
        vm.onInputChange("zelda tips")
        advanceUntilIdle()
        assertEquals("zelda tips", vm.uiState.value.input)
    }

    @Test
    fun `successful send appends user and the streamed AI reply, clears input`() = runTest(scheduler) {
        stubReply("Use bombs on the rocks.")

        val vm = newViewModel()
        vm.onInputChange("How do I beat the boss?")
        vm.sendMessage()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(3, state.messages.size) // greeting + user + ai
        assertEquals(ChatAuthor.USER, state.messages[1].author)
        assertEquals("How do I beat the boss?", state.messages[1].text)
        assertEquals(ChatAuthor.AI, state.messages[2].author)
        assertEquals("Use bombs on the rocks.", state.messages[2].text)
        assertFalse(state.isResponding)
        assertNull(state.streamingText)
        assertEquals("", state.input)
    }

    @Test
    fun `multiple tokens are concatenated into the persisted reply`() = runTest(scheduler) {
        every { chatRepository.streamMessage(any(), any()) } returns
            flowOf(
                ChatStreamEvent.Sources(listOf("Zelda")),
                ChatStreamEvent.Token("Use "),
                ChatStreamEvent.Token("bombs."),
            )

        val vm = newViewModel()
        vm.onInputChange("q")
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals("Use bombs.", vm.uiState.value.messages.last().text)
    }

    @Test
    fun `send trims whitespace before dispatching`() = runTest(scheduler) {
        val messageSlot = slot<String>()
        every { chatRepository.streamMessage(capture(messageSlot), any()) } returns
            flowOf(ChatStreamEvent.Token("ok"))

        val vm = newViewModel()
        vm.onInputChange("   spaced out   ")
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals("spaced out", messageSlot.captured)
        assertEquals("spaced out", vm.uiState.value.messages[1].text)
    }

    @Test
    fun `send passes prior messages as history excluding the new message`() = runTest(scheduler) {
        val historySlot = slot<List<ChatMessage>>()
        every { chatRepository.streamMessage(any(), capture(historySlot)) } returns
            flowOf(ChatStreamEvent.Token("ok"))

        val vm = newViewModel()
        vm.onInputChange("first question")
        vm.sendMessage()
        advanceUntilIdle()

        // Only the seeded greeting precedes the new user message.
        assertEquals(1, historySlot.captured.size)
        assertEquals(ChatAuthor.AI, historySlot.captured[0].author)
    }

    @Test
    fun `blank input is rejected and nothing is sent`() = runTest(scheduler) {
        val vm = newViewModel()
        vm.onInputChange("    ")
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals(1, vm.uiState.value.messages.size)
        verify(exactly = 0) { chatRepository.streamMessage(any(), any()) }
    }

    @Test
    fun `oversized input is rejected and nothing is sent`() = runTest(scheduler) {
        val vm = newViewModel()
        vm.onInputChange("a".repeat(4097)) // MAX_INPUT_LENGTH is 4096
        vm.sendMessage()
        advanceUntilIdle()

        assertEquals(1, vm.uiState.value.messages.size)
        verify(exactly = 0) { chatRepository.streamMessage(any(), any()) }
    }

    @Test
    fun `a second send is ignored while a request is in flight`() = runTest(scheduler) {
        stubReply("ok")

        val vm = newViewModel()
        vm.onInputChange("first")
        vm.sendMessage() // sets isAiTyping synchronously; queues the request
        vm.onInputChange("second")
        vm.sendMessage() // guarded — already responding
        advanceUntilIdle()

        verify(exactly = 1) { chatRepository.streamMessage(any(), any()) }
        val messages = vm.uiState.value.messages
        assertEquals(3, messages.size) // greeting + first + ai, never "second"
        assertEquals("first", messages[1].text)
    }

    @Test
    fun `input is preserved when a send is guarded mid-request`() = runTest(scheduler) {
        stubReply("ok")

        val vm = newViewModel()
        vm.onInputChange("first")
        vm.sendMessage() // first send in flight; clears the input
        vm.onInputChange("second")
        vm.sendMessage() // guarded — must not discard what the user typed next
        advanceUntilIdle()

        assertEquals("second", vm.uiState.value.input)
    }

    @Test
    fun `timeout failure shows the timeout error message`() = runTest(scheduler) {
        assertErrorMessage(
            SocketTimeoutException(),
            "Request timed out. The server may be busy — try again.",
        )
    }

    @Test
    fun `connection failure shows the unreachable-server message`() = runTest(scheduler) {
        assertErrorMessage(
            ConnectException(),
            "Couldn't reach the server. Make sure it's running on your PC.",
        )
    }

    @Test
    fun `generic IO failure shows the unreachable-server message`() = runTest(scheduler) {
        assertErrorMessage(
            IOException(),
            "Couldn't reach the server. Make sure it's running on your PC.",
        )
    }

    @Test
    fun `unexpected failure shows the generic error message`() = runTest(scheduler) {
        assertErrorMessage(RuntimeException("boom"), "Something went wrong. Please try again.")
    }

    @Test
    fun `stopGenerating keeps the partial reply already streamed`() = runTest(scheduler) {
        val gate = CompletableDeferred<Unit>()
        every { chatRepository.streamMessage(any(), any()) } returns
            flow {
                emit(ChatStreamEvent.Token("Partial answer"))
                gate.await() // stay open after the first token until cancelled
                emit(ChatStreamEvent.Token(" — never sent"))
            }

        val vm = newViewModel()
        vm.onInputChange("q")
        vm.sendMessage()
        advanceUntilIdle() // first token streamed; now waiting on the gate

        assertEquals("Partial answer", vm.uiState.value.streamingText)

        vm.stopGenerating()
        advanceUntilIdle()

        val state = vm.uiState.value
        val last = state.messages.last()
        assertEquals(ChatAuthor.AI, last.author)
        assertEquals("Partial answer", last.text) // partial persisted, not discarded
        assertNull(state.streamingText)
        assertFalse(state.isResponding)
    }

    @Test
    fun `submitFeedback records the rating with the preceding user query`() = runTest(scheduler) {
        stubReply("Use bombs.")
        val querySlot = slot<String>()
        val answerSlot = slot<String>()
        val ratingSlot = slot<String>()
        coEvery {
            chatRepository.sendFeedback(capture(querySlot), capture(answerSlot), capture(ratingSlot), any())
        } returns Result.success(Unit)

        val vm = newViewModel()
        vm.onInputChange("how do I win?")
        vm.sendMessage()
        advanceUntilIdle()

        val aiReply = vm.uiState.value.messages.last()
        vm.submitFeedback(aiReply, "up")
        advanceUntilIdle()

        assertEquals("up", vm.uiState.value.feedback[aiReply.id])
        assertEquals("how do I win?", querySlot.captured) // the preceding user turn
        assertEquals("Use bombs.", answerSlot.captured)
        assertEquals("up", ratingSlot.captured)
    }

    @Test
    fun `submitFeedback reverts the optimistic rating when the send fails`() = runTest(scheduler) {
        stubReply("Use bombs.")
        coEvery { chatRepository.sendFeedback(any(), any(), any(), any()) } returns
            Result.failure(IOException("offline"))

        val vm = newViewModel()
        vm.onInputChange("how do I win?")
        vm.sendMessage()
        advanceUntilIdle()

        val aiReply = vm.uiState.value.messages.last()
        vm.submitFeedback(aiReply, "down")
        advanceUntilIdle()

        // The optimistic entry is rolled back so the user can retry.
        assertNull(vm.uiState.value.feedback[aiReply.id])
    }

    @Test
    fun `submitFeedback is a no-op for a message with no preceding user query`() = runTest(scheduler) {
        val vm = newViewModel()
        val greeting = vm.uiState.value.messages.single() // only the AI greeting

        vm.submitFeedback(greeting, "up")
        advanceUntilIdle()

        assertNull(vm.uiState.value.feedback[greeting.id])
        coVerify(exactly = 0) { chatRepository.sendFeedback(any(), any(), any(), any()) }
    }

    @Test
    fun `clearChat resets to a single cleared-chat message`() = runTest(scheduler) {
        val vm = newViewModel()
        vm.clearChat()
        advanceUntilIdle()

        val state = vm.uiState.value
        assertEquals(1, state.messages.size)
        assertEquals(ChatAuthor.AI, state.messages[0].author)
        assertEquals("Chat cleared. What do you want help with?", state.messages[0].text)
        assertFalse(state.isResponding)
    }

    @Test
    fun `clearChat aborts an in-flight request so no stale reply lands`() = runTest(scheduler) {
        val gate = CompletableDeferred<Unit>()
        every { chatRepository.streamMessage(any(), any()) } returns
            flow {
                gate.await() // stay in flight until released
                emit(ChatStreamEvent.Token("late reply"))
            }

        val vm = newViewModel()
        vm.onInputChange("hi")
        vm.sendMessage()
        advanceUntilIdle() // request is in flight, suspended on the gate

        vm.clearChat()
        advanceUntilIdle() // cancels the send, then clears + seeds the cleared message

        val cleared = vm.uiState.value
        assertEquals(1, cleared.messages.size)
        assertEquals("Chat cleared. What do you want help with?", cleared.messages[0].text)
        assertFalse(cleared.isResponding)

        // Releasing the gate must NOT resurrect the cancelled reply.
        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals(1, vm.uiState.value.messages.size)
    }

    @Test
    fun `message ids are unique across a conversation`() = runTest(scheduler) {
        stubReply("ok")

        val vm = newViewModel()
        vm.onInputChange("q")
        vm.sendMessage()
        advanceUntilIdle()

        val ids = vm.uiState.value.messages.map { it.id }
        assertEquals(ids.size, ids.distinct().size)
    }

    /** Sends a message whose stream fails and asserts the rendered AI error text. */
    private fun TestScope.assertErrorMessage(failure: Throwable, expected: String) {
        every { chatRepository.streamMessage(any(), any()) } returns flow { throw failure }

        val vm = newViewModel()
        vm.onInputChange("anything")
        vm.sendMessage()
        advanceUntilIdle()

        val last = vm.uiState.value.messages.last()
        assertEquals(ChatAuthor.AI, last.author)
        assertEquals(expected, last.text)
        assertFalse(vm.uiState.value.isResponding)
    }
}
