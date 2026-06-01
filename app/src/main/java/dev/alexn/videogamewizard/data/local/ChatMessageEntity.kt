package dev.alexn.videogamewizard.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room representation of a chat message. [author] stores the [ChatAuthor] name;
 * [id] is auto-generated and also defines insertion order.
 */
@Entity(tableName = "chat_messages")
data class ChatMessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val author: String,
    val text: String,
    val createdAt: Long,
)
