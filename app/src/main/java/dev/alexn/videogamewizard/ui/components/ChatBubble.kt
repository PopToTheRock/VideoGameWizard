package dev.alexn.videogamewizard.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.alexn.videogamewizard.R
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage

@Composable
fun ChatBubble(message: ChatMessage) {
    val isUser = message.author == ChatAuthor.USER

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        val bubbleShape = RoundedCornerShape(
            topStart = 16.dp,
            topEnd = 16.dp,
            bottomEnd = if (isUser) 4.dp else 16.dp,
            bottomStart = if (isUser) 16.dp else 4.dp,
        )

        val bubbleColor = if (isUser) {
            MaterialTheme.colorScheme.secondaryContainer
        } else {
            MaterialTheme.colorScheme.surface
        }

        Card(
            modifier = Modifier
                .fillMaxWidth(0.85f)
                .clip(bubbleShape),
            shape = bubbleShape,
        ) {
            Column(
                modifier = Modifier
                    .background(bubbleColor)
                    .padding(12.dp),
            ) {
                Text(
                    text = stringResource(
                        if (isUser) R.string.chat_author_user else R.string.chat_author_ai,
                    ),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = message.text,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
        }
    }
}
