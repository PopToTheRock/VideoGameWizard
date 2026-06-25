package dev.alexn.videogamewizard.data.local

import androidx.room.testing.MigrationTestHelper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Verifies the v1 → v2 Room migration ([MIGRATION_1_2]) preserves existing rows
 * and adds the `sources` column (back-filled to ""). Validated against the
 * committed exported schemas in `app/schemas/` (wired as androidTest assets).
 */
@RunWith(AndroidJUnit4::class)
class MigrationTest {

    private val dbName = "migration-test"

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        AppDatabase::class.java,
    )

    @Test
    fun migrate1To2_preservesRows_andBackfillsSourcesColumn() {
        // Create the v1 schema (no `sources` column) and seed two rows.
        helper.createDatabase(dbName, 1).use { db ->
            db.execSQL(
                "INSERT INTO chat_messages (author, text, createdAt) VALUES " +
                    "('AI', 'hello', 100), ('USER', 'hi there', 200)",
            )
        }

        // Apply the migration and validate the result matches the v2 schema.
        val db = helper.runMigrationsAndValidate(dbName, 2, true, MIGRATION_1_2)

        db.query("SELECT author, text, createdAt, sources FROM chat_messages ORDER BY id").use { c ->
            assertEquals(2, c.count) // both rows survived
            assertTrue(c.moveToFirst())
            assertEquals("AI", c.getString(0))
            assertEquals("hello", c.getString(1))
            assertEquals(100L, c.getLong(2))
            assertEquals("", c.getString(3)) // new column back-filled to ""
        }
    }
}
