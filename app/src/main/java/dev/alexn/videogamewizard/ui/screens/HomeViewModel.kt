package dev.alexn.videogamewizard.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import dev.alexn.videogamewizard.VideoGameWizardApp
import dev.alexn.videogamewizard.data.model.ChatAuthor
import dev.alexn.videogamewizard.data.repository.ChatHistoryRepository
import dev.alexn.videogamewizard.data.repository.ChatRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
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
    private data class TransientState(val input: String = "", val isAiTyping: Boolean = false)

    private val transient = MutableStateFlow(TransientState())

    private var sendJob: Job? = null

    // Persisted messages (single source of truth) combined with transient UI state.
    val uiState: StateFlow<HomeUiState> =
        combine(historyRepository.messages, transient) { messages, t ->
            HomeUiState(messages = messages, input = t.input, isAiTyping = t.isAiTyping)
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
        if (transient.value.isAiTyping) return

        val trimmed = transient.value.input.trim()
        // Issue 4: reject empty or oversized input.
        if (trimmed.isEmpty() || trimmed.length > MAX_INPUT_LENGTH) return

        // Context for the model = the conversation shown before this message.
        val history = uiState.value.messages
        // Set typing synchronously so a concurrent send is reliably guarded.
        transient.update { it.copy(input = "", isAiTyping = true) }

        sendJob = viewModelScope.launch {
            historyRepository.append(ChatAuthor.USER, trimmed)
            try {
                val reply =
                    chatRepository.sendMessage(trimmed, history).fold(
                        onSuccess = { it.response },
                        // Issue 5: map the failure to an actionable message.
                        onFailure = { errorMessage(it) },
                    )
                historyRepository.append(ChatAuthor.AI, reply)
                transient.update { it.copy(isAiTyping = false) }
            } catch (e: CancellationException) {
                // Always clear the typing indicator before propagating cancellation.
                transient.update { it.copy(isAiTyping = false) }
                throw e
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
