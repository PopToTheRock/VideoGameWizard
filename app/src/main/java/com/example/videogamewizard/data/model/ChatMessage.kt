package com.example.videogamewizard.data.model

data class ChatMessage(
    val id: Long,
    val author: ChatAuthor,
    val text: String
)
