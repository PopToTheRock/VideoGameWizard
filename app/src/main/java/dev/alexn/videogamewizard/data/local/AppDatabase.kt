package dev.alexn.videogamewizard.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

/**
 * Room database for local chat history.
 *
 * Schema export is on ([exportSchema] = true): each version's schema JSON is
 * written to `app/schemas/` (configured via the `room.schemaLocation` kapt arg)
 * and committed, so any future schema change can ship a real [androidx.room.migration.Migration]
 * against a known baseline. Until then, [DefaultAppContainer] falls back to a
 * destructive migration — acceptable because chat history is local and
 * non-critical (see the rationale there). Bump [version] on every schema change.
 */
@Database(entities = [ChatMessageEntity::class], version = 1, exportSchema = true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun chatDao(): ChatDao
}
