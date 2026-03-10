package com.example.videogamewizard.ui.screens

import com.example.videogamewizard.data.model.ChatAuthor
import com.example.videogamewizard.data.model.ChatMessage

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
