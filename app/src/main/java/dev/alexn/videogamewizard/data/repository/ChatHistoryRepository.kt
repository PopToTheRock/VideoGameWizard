package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import kotlinx.coroutines.flow.Flow

/**
 * Persistent store for the conversation. The single source of truth for
 * displayed messages — the UI observes [messages] and mutates via [append] /
 * [clear]. An interface so it can be backed by Room in production and faked in
 * tests.
 */
interface ChatHistoryRepository {
    /** The full conversation, in order, re-emitting whenever it changes. */
    val messages: Flow<List<ChatMessage>>

    suspend fun append(author: ChatAuthor, text: String)

    suspend fun clear()

    suspend fun count(): Int
}
