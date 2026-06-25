package dev.alexn.videogamewizard.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * Room database for local chat history.
 *
 * Schema export is on ([exportSchema] = true): each version's schema JSON is
 * written to `app/schemas/` (configured via the `room.schemaLocation` kapt arg)
 * and committed, so any future schema change can ship a real [Migration]
 * against a known baseline. [DefaultAppContainer] registers the migrations below
 * and keeps a destructive fallback as a backstop — acceptable because chat
 * history is local and non-critical (see the rationale there). Bump [version]
 * on every schema change.
 */
@Database(entities = [ChatMessageEntity::class], version = 2, exportSchema = true)
abstract class AppDatabase : RoomDatabase() {
    abstract fun chatDao(): ChatDao
}

/**
 * v1 → v2: add the `sources` column (JSON-encoded source titles per message).
 * `NOT NULL DEFAULT ''` is required by SQLite for ADD COLUMN and matches the
 * entity's `@ColumnInfo(defaultValue = "")`, so existing rows back-fill to "".
 */
val MIGRATION_1_2: Migration =
    object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            db.execSQL("ALTER TABLE chat_messages ADD COLUMN sources TEXT NOT NULL DEFAULT ''")
        }
    }
