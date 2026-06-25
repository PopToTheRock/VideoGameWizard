package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.local.ChatDao
import dev.alexn.videogamewizard.data.local.ChatMessageEntity
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.Json

/** Room-backed [ChatHistoryRepository]. */
class RoomChatHistoryRepository(private val dao: ChatDao) : ChatHistoryRepository {

    private val json = Json { ignoreUnknownKeys = true }

    override val messages: Flow<List<ChatMessage>> =
        dao.observeAll().map { rows -> rows.map(::toDomain) }

    override suspend fun append(author: ChatAuthor, text: String, sources: List<String>) {
        dao.insert(
            ChatMessageEntity(
                author = author.name,
                text = text,
                createdAt = System.currentTimeMillis(),
                sources = if (sources.isEmpty()) "" else json.encodeToString(sources),
            ),
        )
    }

    override suspend fun clear() = dao.clear()

    override suspend fun count(): Int = dao.count()

    private fun toDomain(entity: ChatMessageEntity): ChatMessage = ChatMessage(
        id = entity.id,
        // Non-throwing lookup; fall back to AI if a future schema ever stores an
        // unrecognised author (avoids ChatAuthor.valueOf throwing on bad data).
        author = ChatAuthor.entries.firstOrNull { it.name == entity.author } ?: ChatAuthor.AI,
        text = entity.text,
        sources = decodeSources(entity.sources),
    )

    // Tolerant of empty/legacy/corrupt values — a bad row shouldn't crash the list.
    private fun decodeSources(raw: String): List<String> = if (raw.isBlank()) {
        emptyList()
    } else {
        runCatching { json.decodeFromString<List<String>>(raw) }.getOrDefault(emptyList())
    }
}
