package dev.alexn.videogamewizard.ui.screens

import androidx.compose.runtime.Immutable
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage

@Immutable
data class HomeUiState(
    val messages: List<ChatMessage> = listOf(
        ChatMessage(
            id = 1L,
            author = ChatAuthor.AI,
            text = "Hi! Tell me what game you're playing and what you want to improve."
        )
    ),
    val input: String = "",
    val isAiTyping: Boolean = false
)
