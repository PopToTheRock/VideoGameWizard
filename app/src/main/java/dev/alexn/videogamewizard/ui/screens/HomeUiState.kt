package dev.alexn.videogamewizard.ui.screens

import androidx.compose.runtime.Immutable
import dev.alexn.videogamewizard.data.model.ChatMessage

@Immutable
data class HomeUiState(
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    val isAiTyping: Boolean = false,
)
