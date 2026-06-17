package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.network.ChatRequest
import dev.alexn.videogamewizard.data.network.FeedbackRequest
import dev.alexn.videogamewizard.data.network.HistoryMessage
import dev.alexn.videogamewizard.data.network.RagApi
import dev.alexn.videogamewizard.data.network.RetrofitClient
import dev.alexn.videogamewizard.data.network.StreamEvent
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.serialization.json.Json
import java.io.IOException

/** One decoded event from the chat stream, surfaced to the ViewModel. */
sealed interface ChatStreamEvent {
    /** The retrieved source article titles, emitted once before any token. */
    data class Sources(val sources: List<String>) : ChatStreamEvent

    /** An incremental piece of the assistant's answer. */
    data class Token(val text: String) : ChatStreamEvent
}

class ChatRepository(
    private val api: RagApi = RetrofitClient.ragApi,
) {
    private val json = Json { ignoreUnknownKeys = true }

    /**
     * Streams the assistant reply for [message], with [history] as context.
     *
     * Emits a [ChatStreamEvent.Sources] first, then a [ChatStreamEvent.Token] per
     * token; the flow completes normally when the server sends its `done` event.
     * A network failure — or an in-band `error` event — is thrown so the collector
     * can map it to a user-facing message. Cancellation propagates normally: the
     * cold flow is abandoned and the [okhttp3.ResponseBody] is closed by [use],
     * aborting the in-flight HTTP read.
     *
     * Reads run on [Dispatchers.IO] because `readUtf8Line` is a blocking call.
     */
    fun streamMessage(
        message: String,
        history: List<ChatMessage>,
    ): Flow<ChatStreamEvent> = flow {
        val body = api.chatStream(ChatRequest(message = message, history = history.toWire()))
        body.use { responseBody ->
            val source = responseBody.source()
            while (true) {
                val line = source.readUtf8Line() ?: break
                if (line.isBlank()) continue
                val event = json.decodeFromString<StreamEvent>(line)
                when (event.type) {
                    "sources" -> emit(ChatStreamEvent.Sources(event.sources))
                    "token" -> event.token?.let { emit(ChatStreamEvent.Token(it)) }
                    "error" -> throw IOException(event.message ?: "Stream error")
                    "done" -> return@use
                }
            }
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Records a thumbs [rating] ("up"/"down") on [answer] to [query]. Returns a
     * [Result] so the caller can revert an optimistic UI update on failure.
     * CancellationException is rethrown so structured concurrency is preserved.
     */
    suspend fun sendFeedback(
        query: String,
        answer: String,
        rating: String,
        sources: List<String> = emptyList(),
    ): Result<Unit> = try {
        api.sendFeedback(FeedbackRequest(query, answer, rating, sources))
        Result.success(Unit)
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        Result.failure(e)
    }

    private fun List<ChatMessage>.toWire(): List<HistoryMessage> = map { msg ->
        HistoryMessage(
            role = if (msg.author == ChatAuthor.USER) "user" else "assistant",
            content = msg.text,
        )
    }
}
