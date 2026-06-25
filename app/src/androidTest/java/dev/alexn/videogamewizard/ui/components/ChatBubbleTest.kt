package dev.alexn.videogamewizard.ui.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import org.junit.Rule
import org.junit.Test

/** Verifies source-citation chips render for grounded AI replies (and only those). */
class ChatBubbleTest {

    @get:Rule
    val compose = createComposeRule()

    @Test
    fun aiReplyWithSources_rendersSourceChips() {
        compose.setContent {
            ChatBubble(
                message = ChatMessage(
                    id = 1,
                    author = ChatAuthor.AI,
                    text = "Use bombs on the cracked wall.",
                    sources = listOf("The Legend of Zelda", "Super Mario Bros."),
                ),
            )
        }

        compose.onNodeWithText("Sources").assertIsDisplayed()
        compose.onNodeWithText("The Legend of Zelda").assertIsDisplayed()
        compose.onNodeWithText("Super Mario Bros.").assertIsDisplayed()
    }

    @Test
    fun userMessage_doesNotRenderSources() {
        compose.setContent {
            ChatBubble(
                message = ChatMessage(
                    id = 2,
                    author = ChatAuthor.USER,
                    text = "How do I beat the boss?",
                    // Even if a USER row somehow carried sources, they must not show.
                    sources = listOf("Should be ignored"),
                ),
            )
        }

        compose.onNodeWithText("Sources").assertDoesNotExist()
    }
}
