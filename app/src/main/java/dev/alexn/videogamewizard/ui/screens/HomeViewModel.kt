package dev.alexn.videogamewizard.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import dev.alexn.videogamewizard.VideoGameWizardApp
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.model.ChatMessage
import dev.alexn.videogamewizard.data.repository.ChatHistoryRepository
import dev.alexn.videogamewizard.data.repository.ChatRepository
import dev.alexn.videogamewizard.data.repository.ChatStreamEvent
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException

// Issue 4: cap input to prevent oversized requests reaching the server.
private const val MAX_INPUT_LENGTH = 4096

class HomeViewModel(
    private val chatRepository: ChatRepository,
    private val historyRepository: ChatHistoryRepository,
) : ViewModel() {

    /** Transient, in-memory UI state that isn't worth persisting. */
    private data class TransientState(
        val input: String = "",
        // Request sent, awaiting the first token.
        val isAiTyping: Boolean = false,
        // The streaming partial reply; null when not streaming. Persisted to Room
        // only once, on completion — so streaming costs zero per-token DB writes.
        val streamingText: String? = null,
        // Ratings given this session, keyed by AI message id ("up" / "down").
        val feedback: Map<Long, String> = emptyMap(),
    ) {
        /** A reply is in progress while awaiting the first token or streaming. */
        val isResponding: Boolean get() = isAiTyping || streamingText != null
    }

    private val transient = MutableStateFlow(TransientState())

    private var sendJob: Job? = null

    // Persisted messages (single source of truth) combined with transient UI state.
    val uiState: StateFlow<HomeUiState> =
        combine(historyRepository.messages, transient) { messages, t ->
            HomeUiState(
                messages = messages,
                input = t.input,
                isAiTyping = t.isAiTyping,
                streamingText = t.streamingText,
                feedback = t.feedback,
            )
        }.stateIn(viewModelScope, SharingStarted.Eagerly, HomeUiState())

    init {
        // Seed the greeting on first launch only (empty history).
        viewModelScope.launch {
            if (historyRepository.count() == 0) {
                historyRepository.append(ChatAuthor.AI, GREETING)
            }
        }
    }

    fun onInputChange(value: String) {
        transient.update { it.copy(input = value) }
    }

    fun sendMessage() {
        // Issue 1: ignore sends while a request is already in flight. The send
        // button is also disabled, but this guards programmatic calls too.
        if (transient.value.isResponding) return

        val trimmed = transient.value.input.trim()
        // Issue 4: reject empty or oversized input.
        if (trimmed.isEmpty() || trimmed.length > MAX_INPUT_LENGTH) return

        // Context for the model = the conversation shown before this message.
        val history = uiState.value.messages
        // Set typing synchronously so a concurrent send is reliably guarded.
        transient.update { it.copy(input = "", isAiTyping = true, streamingText = null) }

        sendJob = viewModelScope.launch {
            historyRepository.append(ChatAuthor.USER, trimmed)
            val partial = StringBuilder()
            try {
                chatRepository.streamMessage(trimmed, history).collect { event ->
                    when (event) {
                        // Sources are captured here for feature #2 (citations);
                        // not yet rendered.
                        is ChatStreamEvent.Sources -> Unit
                        is ChatStreamEvent.Token -> {
                            partial.append(event.text)
                            // First token: swap the typing indicator for the
                            // growing reply bubble.
                            transient.update {
                                it.copy(isAiTyping = false, streamingText = partial.toString())
                            }
                        }
                    }
                }
                // Stream completed: persist the full reply once, then drop the
                // transient partial so Room becomes the single source of truth.
                historyRepository.append(ChatAuthor.AI, partial.toString())
                transient.update { it.copy(isAiTyping = false, streamingText = null) }
            } catch (e: CancellationException) {
                // Stopped by the user (see stopGenerating) or wiped (clearChat).
                // Persisting the partial, if any, is handled by the caller that
                // cancelled us; here we only clear the in-flight flags.
                transient.update { it.copy(isAiTyping = false, streamingText = null) }
                throw e
            } catch (e: Exception) {
                // Issue 5: map the failure to an actionable message. Keep any
                // text already streamed, then append the error on its own line.
                val errorText =
                    if (partial.isEmpty()) {
                        errorMessage(e)
                    } else {
                        "$partial\n\n${errorMessage(e)}"
                    }
                historyRepository.append(ChatAuthor.AI, errorText)
                transient.update { it.copy(isAiTyping = false, streamingText = null) }
            }
        }
    }

    /**
     * Stops an in-flight reply, keeping whatever was streamed so far. The partial
     * is persisted under [NonCancellable] because the send coroutine's scope is
     * being cancelled — a plain suspend write would itself be cancelled.
     */
    fun stopGenerating() {
        val inFlight = sendJob ?: return
        val partial = transient.value.streamingText
        sendJob = null
        viewModelScope.launch {
            inFlight.cancelAndJoin()
            if (!partial.isNullOrBlank()) {
                withContext(NonCancellable) {
                    historyRepository.append(ChatAuthor.AI, partial)
                }
            }
            transient.update { it.copy(isAiTyping = false, streamingText = null) }
        }
    }

    /**
     * Records a thumbs [rating] ("up"/"down") on [aiMessage]. The prompt logged
     * with it is the most recent user message before this reply. The tap is
     * reflected optimistically and reverted if the network call fails.
     */
    fun submitFeedback(aiMessage: ChatMessage, rating: String) {
        val messages = uiState.value.messages
        val index = messages.indexOfFirst { it.id == aiMessage.id }
        if (index < 0) return
        val query = messages.subList(0, index).lastOrNull { it.author == ChatAuthor.USER }?.text
            ?: return // no preceding user turn (e.g. the greeting) — nothing to rate

        transient.update { it.copy(feedback = it.feedback + (aiMessage.id to rating)) }
        viewModelScope.launch {
            // Sources aren't persisted with messages yet, so none are sent for now
            // (feature #2 will carry them through and enrich the feedback record).
            val result = chatRepository.sendFeedback(query, aiMessage.text, rating, emptyList())
            if (result.isFailure) {
                transient.update { it.copy(feedback = it.feedback - aiMessage.id) }
            }
        }
    }

    fun clearChat() {
        // Abort any in-flight request first so its (now-stale) reply can't land
        // after the wipe, then reset to a single cleared-chat message.
        val inFlight = sendJob
        sendJob = null
        viewModelScope.launch {
            inFlight?.cancelAndJoin()
            historyRepository.clear()
            historyRepository.append(ChatAuthor.AI, CLEARED)
        }
        transient.update { it.copy(isAiTyping = false) }
    }

    // Issue 5: differentiate error types so the user knows whether to retry,
    // check their connection, or wait for the server.
    private fun errorMessage(exception: Throwable): String = when (exception) {
        is SocketTimeoutException ->
            "Request timed out. The server may be busy — try again."
        is ConnectException, is IOException ->
            "Couldn't reach the server. Make sure it's running on your PC."
        else ->
            "Something went wrong. Please try again."
    }

    companion object {
        private const val GREETING =
            "Hi! Tell me what game you're playing and what you want to improve."
        private const val CLEARED = "Chat cleared. What do you want help with?"

        /** Manual-DI factory: pulls repositories from the app's AppContainer. */
        val Factory: ViewModelProvider.Factory = viewModelFactory {
            initializer {
                val app =
                    this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY]
                        as VideoGameWizardApp
                HomeViewModel(
                    chatRepository = app.container.chatRepository,
                    historyRepository = app.container.chatHistoryRepository,
                )
            }
        }
    }
}
