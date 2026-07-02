package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.network.ChatRequest
import dev.alexn.videogamewizard.data.network.RagApi
import io.mockk.coEvery
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class ChatRepositoryTest {
    private val api: RagApi = mockk()
    private val repository = ChatRepository(api)

    /** Builds an NDJSON [ResponseBody] from raw event lines, as the server sends. */
    private fun ndjsonBody(vararg lines: String): ResponseBody = lines.joinToString(separator = "\n", postfix = "\n")
        .toResponseBody("application/x-ndjson".toMediaType())

    @Test
    fun `stream yields sources then tokens and completes on done`() = runTest {
        coEvery { api.chatStream(any()) } returns ndjsonBody(
            """{"type":"sources","sources":["Mario","Zelda"]}""",
            """{"type":"token","token":"Use "}""",
            """{"type":"token","token":"bombs."}""",
            """{"type":"done"}""",
        )

        val events = repository.streamMessage("question", emptyList()).toList()

        assertEquals(ChatStreamEvent.Sources(listOf("Mario", "Zelda")), events.first())
        val text = events.filterIsInstance<ChatStreamEvent.Token>().joinToString("") { it.text }
        assertEquals("Use bombs.", text)
        // `done` completes the flow rather than emitting a terminal event.
        assertTrue(events.none { it !is ChatStreamEvent.Sources && it !is ChatStreamEvent.Token })
    }

    @Test
    fun `chat messages are mapped to the request with correct roles`() = runTest {
        val requestSlot = slot<ChatRequest>()
        coEvery { api.chatStream(capture(requestSlot)) } returns ndjsonBody("""{"type":"done"}""")

        val history =
            listOf(
                ChatMessage(id = 1, author = ChatAuthor.AI, text = "greeting"),
                ChatMessage(id = 2, author = ChatAuthor.USER, text = "earlier question"),
            )
        repository.streamMessage("current question", history).toList()

        val request = requestSlot.captured
        assertEquals("current question", request.message)
        assertEquals(2, request.history.size)
        assertEquals("assistant", request.history[0].role) // AI -> assistant
        assertEquals("greeting", request.history[0].content)
        assertEquals("user", request.history[1].role) // USER -> user
        assertEquals("earlier question", request.history[1].content)
    }

    @Test
    fun `an in-band error event is thrown to the collector`() = runTest {
        coEvery { api.chatStream(any()) } returns ndjsonBody(
            """{"type":"sources","sources":[]}""",
            """{"type":"error","message":"Ollama request failed"}""",
        )

        val error = runCatching { repository.streamMessage("q", emptyList()).toList() }
            .exceptionOrNull()
        assertTrue(error is IOException)
        assertEquals("Ollama request failed", error?.message)
    }

    @Test
    fun `a network exception propagates from the flow`() = runTest {
        coEvery { api.chatStream(any()) } throws IOException("connection reset")

        val error = runCatching { repository.streamMessage("q", emptyList()).toList() }
            .exceptionOrNull()
        assertTrue(error is IOException)
    }

    @Test
    fun `sendFeedback posts the rating and returns success`() = runTest {
        val requestSlot = slot<dev.alexn.videogamewizard.data.network.FeedbackRequest>()
        coEvery { api.sendFeedback(capture(requestSlot)) } returns
            dev.alexn.videogamewizard.data.network.FeedbackResponse(status = "recorded")

        val result = repository.sendFeedback("how do I win?", "use bombs", "up", listOf("Zelda"))

        assertTrue(result.isSuccess)
        val request = requestSlot.captured
        assertEquals("how do I win?", request.query)
        assertEquals("use bombs", request.answer)
        assertEquals("up", request.rating)
        assertEquals(listOf("Zelda"), request.sources)
    }

    @Test
    fun `sendFeedback captures a network failure as Result-failure`() = runTest {
        coEvery { api.sendFeedback(any()) } throws IOException("offline")

        val result = repository.sendFeedback("q", "a", "down")

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is IOException)
    }

    /** Delegating [ResponseBody] that records whether close() was called. */
    private class TrackingResponseBody(private val delegate: ResponseBody) : ResponseBody() {
        @Volatile var closed = false

        override fun contentType() = delegate.contentType()

        override fun contentLength() = delegate.contentLength()

        override fun source() = delegate.source()

        override fun close() {
            closed = true
            delegate.close()
        }
    }

    @Test
    fun `cancelling collection closes the response body`() = runBlocking {
        // No `done` line: from the client's perspective the stream is still in
        // flight when the collector cancels after the first event.
        val body = TrackingResponseBody(
            ndjsonBody(
                """{"type":"sources","sources":[]}""",
                """{"type":"token","token":"Use "}""",
            ),
        )
        coEvery { api.chatStream(any()) } returns body

        repository.streamMessage("q", emptyList()).first() // take one event, then cancel

        // The close runs on the producer's IO dispatcher; give it a moment.
        val deadline = System.currentTimeMillis() + 2_000
        while (!body.closed && System.currentTimeMillis() < deadline) delay(5)
        assertTrue(body.closed)
    }

    @Test
    fun `empty history produces an empty request history`() = runTest {
        val requestSlot = slot<ChatRequest>()
        coEvery { api.chatStream(capture(requestSlot)) } returns ndjsonBody("""{"type":"done"}""")

        repository.streamMessage("solo question", emptyList()).toList()

        assertTrue(requestSlot.captured.history.isEmpty())
    }
}
