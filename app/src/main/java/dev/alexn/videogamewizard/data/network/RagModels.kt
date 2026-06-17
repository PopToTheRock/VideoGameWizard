package dev.alexn.videogamewizard.data.network

import kotlinx.serialization.Serializable

@Serializable
data class HistoryMessage(
    val role: String,
    val content: String,
)

@Serializable
data class ChatRequest(
    val message: String,
    val history: List<HistoryMessage> = emptyList(),
)

@Serializable
data class ChatResponse(
    val response: String,
    val sources: List<String> = emptyList(),
)

@Serializable
data class FeedbackRequest(
    val query: String,
    val answer: String,
    // "up" or "down" — matches the server's Literal contract.
    val rating: String,
    val sources: List<String> = emptyList(),
)

@Serializable
data class FeedbackResponse(
    val status: String,
)

/**
 * One event from the `/chat/stream` NDJSON stream. [type] is the discriminator:
 * `sources` (carries [sources]), `token` (carries [token]), `done`, or `error`
 * (carries [message]). Fields not relevant to a given type are null/empty.
 */
@Serializable
data class StreamEvent(
    val type: String,
    val token: String? = null,
    val sources: List<String> = emptyList(),
    val message: String? = null,
)
