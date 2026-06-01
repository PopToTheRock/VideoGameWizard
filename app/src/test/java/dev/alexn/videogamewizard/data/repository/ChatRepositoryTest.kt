package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.network.ChatRequest
import dev.alexn.videogamewizard.data.network.ChatResponse
import dev.alexn.videogamewizard.data.network.RagApi
import io.mockk.coEvery
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class ChatRepositoryTest {

    private val api: RagApi = mockk()
    private val repository = ChatRepository(api)

    @Test
    fun `successful call returns the response wrapped in Result-success`() = runTest {
        coEvery { api.chat(any()) } returns ChatResponse(response = "answer", sources = listOf("Zelda"))

        val result = repository.sendMessage("question", emptyList())

        assertTrue(result.isSuccess)
        assertEquals("answer", result.getOrNull()?.response)
        assertEquals(listOf("Zelda"), result.getOrNull()?.sources)
    }

    @Test
    fun `chat messages are mapped to the request with correct roles`() = runTest {
        val requestSlot = slot<ChatRequest>()
        coEvery { api.chat(capture(requestSlot)) } returns ChatResponse(response = "ok")

        val history = listOf(
            ChatMessage(id = 1, author = ChatAuthor.AI, text = "greeting"),
            ChatMessage(id = 2, author = ChatAuthor.USER, text = "earlier question"),
        )
        repository.sendMessage("current question", history)

        val request = requestSlot.captured
        assertEquals("current question", request.message)
        assertEquals(2, request.history.size)
        assertEquals("assistant", request.history[0].role) // AI -> assistant
        assertEquals("greeting", request.history[0].content)
        assertEquals("user", request.history[1].role)       // USER -> user
        assertEquals("earlier question", request.history[1].content)
    }

    @Test
    fun `network exception is captured as Result-failure`() = runTest {
        coEvery { api.chat(any()) } throws IOException("connection reset")

        val result = repository.sendMessage("question", emptyList())

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is IOException)
    }

    @Test
    fun `cancellation is rethrown, never swallowed into a Result`() = runTest {
        coEvery { api.chat(any()) } throws CancellationException("scope cancelled")

        var rethrown = false
        try {
            repository.sendMessage("question", emptyList())
        } catch (e: CancellationException) {
            rethrown = true
        }

        // If cancellation had been wrapped in Result.failure, nothing would throw.
        assertTrue(rethrown)
    }

    @Test
    fun `empty history produces an empty request history`() = runTest {
        val requestSlot = slot<ChatRequest>()
        coEvery { api.chat(capture(requestSlot)) } returns ChatResponse(response = "ok")

        repository.sendMessage("solo question", emptyList())

        assertFalse(requestSlot.captured.history.isNotEmpty())
    }
}
