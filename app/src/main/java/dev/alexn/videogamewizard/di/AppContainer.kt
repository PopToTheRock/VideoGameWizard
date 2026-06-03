package dev.alexn.videogamewizard.di

import android.content.Context
import androidx.room.Room
import dev.alexn.videogamewizard.data.local.AppDatabase
import dev.alexn.videogamewizard.data.repository.ChatHistoryRepository
import dev.alexn.videogamewizard.data.repository.ChatRepository
import dev.alexn.videogamewizard.data.repository.RoomChatHistoryRepository

/**
 * Manual dependency-injection container (the "AppContainer" pattern from
 * Google's architecture guidance). Holds app-scoped singletons and wires the
 * Room database into the repositories. Created once in [VideoGameWizardApp].
 */
interface AppContainer {
    val chatRepository: ChatRepository
    val chatHistoryRepository: ChatHistoryRepository
}

class DefaultAppContainer(context: Context) : AppContainer {

    private val database: AppDatabase by lazy {
        Room.databaseBuilder(
            context.applicationContext,
            AppDatabase::class.java,
            "videogamewizard.db",
        )
            // Migration strategy: until a schema change actually warrants a
            // hand-written Migration, drop and recreate. This is a deliberate
            // trade-off — chat history is local, non-critical, and cheap to
            // lose, so the simplicity is worth more than preserving old rows.
            // The exported schemas (see AppDatabase) make swapping in a real
            // Migration straightforward when that calculus changes.
            .fallbackToDestructiveMigration(dropAllTables = true)
            .build()
    }

    override val chatRepository: ChatRepository by lazy { ChatRepository() }

    override val chatHistoryRepository: ChatHistoryRepository by lazy {
        RoomChatHistoryRepository(database.chatDao())
    }
}
