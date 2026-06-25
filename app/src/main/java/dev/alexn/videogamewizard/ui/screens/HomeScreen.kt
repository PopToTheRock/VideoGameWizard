package dev.alexn.videogamewizard.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import dev.alexn.videogamewizard.R
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.ui.components.ChatBubble
import dev.alexn.videogamewizard.ui.components.MessageFeedback
import dev.alexn.videogamewizard.ui.components.TypingIndicatorBubble
import dev.alexn.videogamewizard.ui.components.UserChatFieldComposer
import dev.alexn.videogamewizard.ui.theme.Purple40
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

// Stable list key for the transient streaming bubble. Negative so it can never
// collide with a Room-generated (positive, auto-increment) message id.
private const val STREAMING_MESSAGE_ID = -1L

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onBack: () -> Unit,
    viewModel: HomeViewModel = viewModel(factory = HomeViewModel.Factory),
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    // Open a cited source's Wikipedia article (the corpus is English Wikipedia),
    // satisfying the CC BY-SA attribution link-back. No-op if no browser handles it.
    val onSourceClick: (String) -> Unit = remember(context) {
        { title ->
            val url = "https://en.wikipedia.org/wiki/" + Uri.encode(title.replace(' ', '_'))
            runCatching {
                context.startActivity(
                    Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
            }
        }
    }

    // Index of the newest item to scroll to: the trailing typing/streaming item
    // when present, otherwise the last message.
    val hasTrailingItem = uiState.isAiTyping || uiState.streamingText != null
    val targetIndex =
        if (hasTrailingItem) uiState.messages.size else uiState.messages.lastIndex

    // True when the last list item is visible — i.e. the user is at the bottom.
    // derivedStateOf so it only recomposes readers when the boolean flips, not on
    // every scroll pixel.
    val isAtBottom by remember {
        derivedStateOf {
            val info = listState.layoutInfo
            val lastVisible = info.visibleItemsInfo.lastOrNull()
            lastVisible == null || lastVisible.index >= info.totalItemsCount - 1
        }
    }

    // On first open, jump to the latest message once the history has loaded.
    // Instant (not animated) so the screen simply starts at the bottom. Runs once.
    LaunchedEffect(Unit) {
        val count = snapshotFlow { uiState.messages.size }.first { it > 0 }
        listState.scrollToItem(count - 1)
    }

    // A new persisted message: always jump when it's the user's own send; for an
    // AI message, only follow if the user is already at the bottom. Keying on the
    // id (not size) also catches in-place replacements, e.g. an error bubble.
    val lastMessageId = uiState.messages.lastOrNull()?.id
    val lastIsUser = uiState.messages.lastOrNull()?.author == ChatAuthor.USER
    LaunchedEffect(lastMessageId) {
        if (targetIndex >= 0 && (isAtBottom || lastIsUser)) {
            listState.animateScrollToItem(targetIndex)
        }
    }

    // Streaming tokens / typing indicator: follow the growing reply only while
    // the user is at the bottom, so scrolling up to read history isn't yanked
    // back down on every token.
    LaunchedEffect(uiState.streamingText?.length, uiState.isAiTyping) {
        if (targetIndex >= 0 && isAtBottom) {
            listState.animateScrollToItem(targetIndex)
        }
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        // Fill the whole window — including behind the transparent system bars —
        // with the app background, so the edge-to-edge nav bar shows the purple
        // backdrop instead of the theme's default (white) window background.
        containerColor = Purple40,
        topBar = {
            Surface(
                color = MaterialTheme.colorScheme.primary,
                contentColor = Color.White,
                shadowElevation = 6.dp,
            ) {
                TopAppBar(
                    title = { Text(stringResource(R.string.chat_title)) },
                    navigationIcon = {
                        IconButton(onClick = onBack) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = stringResource(R.string.cd_back),
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = viewModel::clearChat) {
                            Icon(
                                imageVector = Icons.Filled.Delete,
                                contentDescription = stringResource(R.string.cd_clear_chat),
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent,
                    ),
                )
            }
        },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                // Mark the Scaffold insets as consumed so imePadding() adds only
                // the keyboard height *beyond* the nav-bar inset already applied
                // above — otherwise the bottom inset is double-counted when the
                // keyboard opens, leaving a large gap above it.
                .consumeWindowInsets(innerPadding)
                .imePadding()
                .testTag("home_screen"),
        ) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
            ) {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    state = listState,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    itemsIndexed(items = uiState.messages, key = { _, m -> m.id }) { index, msg ->
                        ChatBubble(message = msg, onSourceClick = onSourceClick)
                        // Offer feedback on AI replies only — i.e. an AI message
                        // with a user turn before it (skips the greeting/cleared).
                        val isReply = msg.author == ChatAuthor.AI &&
                            uiState.messages.take(index).any { it.author == ChatAuthor.USER }
                        if (isReply) {
                            MessageFeedback(
                                rating = uiState.feedback[msg.id],
                                onRate = { viewModel.submitFeedback(msg, it) },
                            )
                        }
                    }

                    // The streaming reply renders as a normal AI bubble that grows
                    // token by token; it's transient until persisted on completion.
                    uiState.streamingText?.let { partial ->
                        item(key = "streaming") {
                            ChatBubble(
                                message = ChatMessage(
                                    id = STREAMING_MESSAGE_ID,
                                    author = ChatAuthor.AI,
                                    text = partial,
                                    sources = uiState.streamingSources,
                                ),
                                onSourceClick = onSourceClick,
                            )
                        }
                    }

                    if (uiState.isAiTyping) {
                        item(key = "typing") {
                            TypingIndicatorBubble()
                        }
                    }
                }

                // Pops up only when the user has scrolled away from the latest
                // message; tapping it animates back to the bottom.
                ScrollToBottomButton(
                    visible = !isAtBottom,
                    onClick = {
                        scope.launch {
                            if (targetIndex >= 0) listState.animateScrollToItem(targetIndex)
                        }
                    },
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(12.dp),
                )
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.12f))

            UserChatFieldComposer(
                value = uiState.input,
                onValueChange = viewModel::onInputChange,
                onSend = viewModel::sendMessage,
                onStop = viewModel::stopGenerating,
                isResponding = uiState.isResponding,
            )
        }
    }
}

/**
 * A small FAB that fades/scales in when [visible], scrolling the chat to the
 * latest message on tap. Extracted from [HomeScreen] so the top-level
 * `AnimatedVisibility` overload resolves cleanly (inside a `Box` nested in a
 * `Column`, the `ColumnScope` extension would otherwise be picked).
 */
@Composable
private fun ScrollToBottomButton(
    visible: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = visible,
        enter = scaleIn() + fadeIn(),
        exit = scaleOut() + fadeOut(),
        modifier = modifier,
    ) {
        SmallFloatingActionButton(
            onClick = onClick,
            containerColor = MaterialTheme.colorScheme.primary,
            contentColor = Color.White,
        ) {
            Icon(
                imageVector = Icons.Filled.KeyboardArrowDown,
                contentDescription = stringResource(R.string.cd_scroll_to_bottom),
            )
        }
    }
}
