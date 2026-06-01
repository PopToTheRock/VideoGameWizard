package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.network.ChatRequest
import dev.alexn.videogamewizard.data.network.ChatResponse
import dev.alexn.videogamewizard.data.network.HistoryMessage
import dev.alexn.videogamewizard.data.network.RagApi
import dev.alexn.videogamewizard.data.network.RetrofitClient
import kotlinx.coroutines.CancellationException

class ChatRepository(
    private val api: RagApi = RetrofitClient.ragApi,
) {
    /**
     * Sends [message] to the RAG server along with [history] for context.
     * Returns a [Result] wrapping the server response.
     *
     * CancellationException is always rethrown so structured concurrency is
     * not broken — coroutine cancellation must propagate normally.
     */
    suspend fun sendMessage(
        message: String,
        history: List<ChatMessage>,
    ): Result<ChatResponse> = try {
        Result.success(
            api.chat(
                ChatRequest(
                    message = message,
                    history =
                    history.map { msg ->
                        HistoryMessage(
                            role = if (msg.author == ChatAuthor.USER) "user" else "assistant",
                            content = msg.text,
                        )
                    },
                ),
            ),
        )
    } catch (e: CancellationException) {
        throw e // must not be swallowed — lets the coroutine cancel cleanly
    } catch (e: Exception) {
        Result.failure(e)
    }
}
