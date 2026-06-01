package dev.alexn.videogamewizard.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface ChatDao {
    /** Emits the full conversation in insertion order, re-emitting on any change. */
    @Query("SELECT * FROM chat_messages ORDER BY id ASC")
    fun observeAll(): Flow<List<ChatMessageEntity>>

    @Insert
    suspend fun insert(message: ChatMessageEntity): Long

    @Query("DELETE FROM chat_messages")
    suspend fun clear()

    @Query("SELECT COUNT(*) FROM chat_messages")
    suspend fun count(): Int
}
