package dev.alexn.videogamewizard.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(entities = [ChatMessageEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun chatDao(): ChatDao
}
