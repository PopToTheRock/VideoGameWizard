package com.example.videogamewizard.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.videogamewizard.ui.components.ChatBubble
import com.example.videogamewizard.ui.components.TypingIndicatorBubble
import com.example.videogamewizard.ui.components.UserChatFieldComposer
import com.example.videogamewizard.ui.theme.Purple40

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onBack: () -> Unit,
    viewModel: HomeViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.lastIndex)
        }
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            Surface(
                color = MaterialTheme.colorScheme.primary,
                contentColor = Color.White,
                shadowElevation = 6.dp
            ) {
                TopAppBar(
                    title = { Text("AI Chat") },
                    navigationIcon = {
                        IconButton(onClick = onBack) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = "Back"
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = viewModel::clearChat) {
                            Icon(
                                imageVector = Icons.Filled.Delete,
                                contentDescription = "Clear chat"
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent
                    )
                )
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(color = Purple40)
                .padding(innerPadding)
                .imePadding()
                .testTag("home_screen")
        ) {
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(items = uiState.messages, key = { it.id }) { msg ->
                    ChatBubble(message = msg)
                }

                if (uiState.isAiTyping) {
                    item(key = "typing") {
                        TypingIndicatorBubble()
                    }
                }
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.12f))

            UserChatFieldComposer(
                value = uiState.input,
                onValueChange = viewModel::onInputChange,
                onSend = viewModel::sendMessage,
                enabled = !uiState.isAiTyping
            )
        }
    }
}
