package dev.alexn.videogamewizard.data.repository

import dev.alexn.videogamewizard.data.local.ChatDao
import dev.alexn.videogamewizard.data.local.ChatMessageEntity
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/** Room-backed [ChatHistoryRepository]. */
class RoomChatHistoryRepository(private val dao: ChatDao) : ChatHistoryRepository {

    override val messages: Flow<List<ChatMessage>> =
        dao.observeAll().map { rows -> rows.map(::toDomain) }

    override suspend fun append(author: ChatAuthor, text: String) {
        dao.insert(
            ChatMessageEntity(
                author = author.name,
                text = text,
                createdAt = System.currentTimeMillis(),
            ),
        )
    }

    override suspend fun clear() = dao.clear()

    override suspend fun count(): Int = dao.count()

    private fun toDomain(entity: ChatMessageEntity): ChatMessage = ChatMessage(
        id = entity.id,
        author = ChatAuthor.valueOf(entity.author),
        text = entity.text,
    )
}
