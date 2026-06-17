package dev.alexn.videogamewizard.ui.components

import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.outlined.ThumbDown
import androidx.compose.material.icons.outlined.ThumbUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.alexn.videogamewizard.R

/** Rating values sent to the server; mirror the backend's `Literal["up","down"]`. */
const val RATING_UP = "up"
const val RATING_DOWN = "down"

/**
 * Thumbs up/down row shown under an AI answer. The chosen rating renders filled;
 * tapping either calls [onRate] with [RATING_UP] / [RATING_DOWN].
 */
@Composable
fun MessageFeedback(
    rating: String?,
    onRate: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(modifier = modifier) {
        IconButton(onClick = { onRate(RATING_UP) }) {
            Icon(
                imageVector =
                if (rating == RATING_UP) Icons.Filled.ThumbUp else Icons.Outlined.ThumbUp,
                contentDescription = stringResource(R.string.cd_thumb_up),
                tint = Color.White.copy(alpha = if (rating == RATING_UP) 1f else 0.6f),
                modifier = Modifier.size(20.dp),
            )
        }
        IconButton(onClick = { onRate(RATING_DOWN) }) {
            Icon(
                imageVector =
                if (rating == RATING_DOWN) Icons.Filled.ThumbDown else Icons.Outlined.ThumbDown,
                contentDescription = stringResource(R.string.cd_thumb_down),
                tint = Color.White.copy(alpha = if (rating == RATING_DOWN) 1f else 0.6f),
                modifier = Modifier.size(20.dp),
            )
        }
    }
}
