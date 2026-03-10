package com.example.videogamewizard

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.videogamewizard.ui.theme.VideoGameWizardTheme
import com.example.videogamewizard.ui.theme.Purple40
import com.example.videogamewizard.ui.theme.PurpleGrey40
import com.example.videogamewizard.ui.theme.PurpleGrey80
import kotlinx.coroutines.delay

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VideoGameWizardTheme {
                AppNavGraph()
            }
        }
    }
}

@Composable
fun WelcomeScreen(onGetStarted: () -> Unit) {
    Scaffold(modifier = Modifier
        .fillMaxSize()
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .testTag("welcome_screen")
                .background(color = Purple40)
                .padding(innerPadding)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .wrapContentSize(Alignment.Center)
            ) {
                Box(
                    modifier = Modifier
                        .border(
                            width = 4.dp,
                            color = PurpleGrey40,
                            shape = RoundedCornerShape(16.dp)
                        )
                        .background(
                            shape = RoundedCornerShape(16.dp),
                            color = PurpleGrey80
                        )
                        .padding(16.dp),
                        contentAlignment = Alignment.Center
                ) {
                        Text(
                            text = "Welcome to Video Game Wizard!",
                            color = Color.DarkGray
                        )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = {onGetStarted()},
                    modifier = Modifier
                        .width(200.dp)
                        .height(50.dp)
                        .align(alignment = Alignment.CenterHorizontally)
                ) {
                    Text(
                        text = "Get Started",
                        color = Color.White
                    )
                }
            }
        }

    }
}

private enum class ChatAuthor { USER, AI }

private data class ChatMessage(
    val id: Long,
    val author: ChatAuthor,
    val text: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(onBack: () -> Unit) {
    val messages = remember {
        mutableStateListOf(
            ChatMessage(
                id = 1L,
                author = ChatAuthor.AI,
                text = "Hi! Tell me what game you’re playing and what you want to improve."
            )
        )
    }
    var input by remember { mutableStateOf("") }
    var aiTyping by remember { mutableStateOf(false) }

    val listState = rememberLazyListState()

    fun sendUserMessage() {
        val trimmed = input.trim()
        if (trimmed.isEmpty()) return

        messages += ChatMessage(
            id = System.currentTimeMillis(),
            author = ChatAuthor.USER,
            text = trimmed
        )
        input = ""

        // UI-only stub reply (replace with your real AI call later)
        aiTyping = true
    }

    LaunchedEffect(messages.size, aiTyping) {
        if (aiTyping) {
            delay(600)
            messages += ChatMessage(
                id = System.currentTimeMillis(),
                author = ChatAuthor.AI,
                text = "Got it. What platform (PC/PS/Xbox/Switch/mobile) and what’s your goal (rank up, build optimization, walkthrough, etc.)?"
            )
            aiTyping = false
        }
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.lastIndex)
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
                        IconButton(
                            onClick = {
                                messages.clear()
                                messages += ChatMessage(
                                    id = System.currentTimeMillis(),
                                    author = ChatAuthor.AI,
                                    text = "Chat cleared. What do you want help with?"
                                )
                            }
                        ) {
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
                .windowInsetsPadding(WindowInsets.safeDrawing)
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
                items(items = messages, key = { it.id }) { msg ->
                    ChatBubble(message = msg)
                }

                if (aiTyping) {
                    item(key = "typing") {
                        TypingIndicatorBubble()
                    }
                }
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.12f))

            UserChatFieldComposer(
                value = input,
                onValueChange = { input = it },
                onSend = { sendUserMessage() },
                enabled = !aiTyping
            )
        }
    }
}

@Composable
private fun ChatBubble(message: ChatMessage) {
    val isUser = message.author == ChatAuthor.USER

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        val bubbleShape = RoundedCornerShape(
            topStart = 16.dp,
            topEnd = 16.dp,
            bottomEnd = if (isUser) 4.dp else 16.dp,
            bottomStart = if (isUser) 16.dp else 4.dp
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
            shape = bubbleShape
        ) {
            Column(
                modifier = Modifier
                    .background(bubbleColor)
                    .padding(12.dp)
            ) {
                Text(
                    text = if (isUser) "You" else "Wizard AI",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f)
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = message.text,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}

@Composable
private fun TypingIndicatorBubble() {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Card(
            modifier = Modifier.fillMaxWidth(0.6f),
            shape = RoundedCornerShape(16.dp)
        ) {
            Column(
                modifier = Modifier
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(12.dp)
            ) {
                Text(
                    text = "Wizard AI",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f)
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = "Typing…",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f)
                )
            }
        }
    }
}

@Composable
private fun UserChatFieldComposer(
    value: String,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
    enabled: Boolean
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        OutlinedTextField(
            modifier = Modifier.weight(1f),
            value = value,
            onValueChange = onValueChange,
            enabled = enabled,
            label = { Text("Message") },
            singleLine = true
        )
        Spacer(Modifier.width(8.dp))
        IconButton(
            onClick = onSend,
            enabled = enabled && value.isNotBlank()
        ) {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.Send,
                contentDescription = "Send"
            )
        }
    }
}

@Composable
fun AppNavGraph(navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = "welcome") {
        composable("welcome") {
            WelcomeScreen(onGetStarted = { navController.navigate("home") })
        }
        composable("home") {
            HomeScreen(onBack = { navController.navigateUp() })
        }
    }
}

@Preview(showBackground = true)
@Composable
fun TestPreview() {
    VideoGameWizardTheme {
        WelcomeScreen(onGetStarted = {})
    }
}