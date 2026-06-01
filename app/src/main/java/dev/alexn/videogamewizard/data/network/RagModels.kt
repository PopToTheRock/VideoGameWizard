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
