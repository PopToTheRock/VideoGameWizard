package dev.alexn.videogamewizard.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room representation of a chat message. [author] stores the [ChatAuthor] name;
 * [id] is auto-generated and also defines insertion order. [sources] is a
 * JSON-encoded list of source article titles for an AI reply (empty otherwise);
 * the JSON (de)serialisation lives in [dev.alexn.videogamewizard.data.repository.RoomChatHistoryRepository].
 *
 * The `defaultValue = ""` matches the `MIGRATION_1_2` ADD COLUMN default so Room's
 * schema validation is satisfied (see [AppDatabase]).
 */
@Entity(tableName = "chat_messages")
data class ChatMessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val author: String,
    val text: String,
    val createdAt: Long,
    @ColumnInfo(defaultValue = "") val sources: String = "",
)
