package dev.alexn.videogamewizard.data.model

import androidx.compose.runtime.Immutable

/**
 * A single chat message. Marked [Immutable] so the Compose compiler can skip
 * recomposition of composables that read an unchanged instance.
 */
@Immutable
data class ChatMessage(
    val id: Long,
    val author: ChatAuthor,
    val text: String
)
