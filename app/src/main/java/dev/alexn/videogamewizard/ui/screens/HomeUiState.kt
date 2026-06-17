package dev.alexn.videogamewizard.ui.screens

import androidx.compose.runtime.Immutable
import dev.alexn.videogamewizard.data.model.ChatMessage

@Immutable
data class HomeUiState(
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    // True once a request is sent but before the first token arrives (shows the
    // animated typing indicator).
    val isAiTyping: Boolean = false,
    // The assistant's partial reply as tokens stream in; null when not streaming.
    // Persisted to [messages] only once the stream completes.
    val streamingText: String? = null,
    // Ratings the user has given, keyed by AI message id ("up" / "down").
    val feedback: Map<Long, String> = emptyMap(),
) {
    /** A reply is in progress while we're awaiting the first token or streaming. */
    val isResponding: Boolean get() = isAiTyping || streamingText != null
}
