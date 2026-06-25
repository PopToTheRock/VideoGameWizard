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
    val text: String,
    // Source article titles that grounded this answer (AI messages only; empty
    // otherwise). Surfaced as citation chips and carried into feedback records.
    val sources: List<String> = emptyList(),
)
