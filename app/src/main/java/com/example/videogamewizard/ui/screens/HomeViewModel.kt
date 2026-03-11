package com.example.videogamewizard.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.videogamewizard.data.model.ChatAuthor
import com.example.videogamewizard.data.model.ChatMessage
import com.example.videogamewizard.data.repository.ChatRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.IOException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicLong

// Issue 4: cap input to prevent oversized requests reaching the server
private const val MAX_INPUT_LENGTH = 4096

class HomeViewModel(
    private val repository: ChatRepository = ChatRepository(),
) : ViewModel() {

    // Issue 3: atomic counter guarantees unique, collision-free IDs
    // regardless of how quickly messages are created
    private val idCounter = AtomicLong(0)
    private fun nextId() = idCounter.getAndIncrement()

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    fun onInputChange(value: String) {
        _uiState.update { it.copy(input = value) }
    }

    fun sendMessage() {
        // Issue 1: guard against concurrent sends — if a request is already
        // in flight, ignore subsequent calls until it completes.
        // The UI also disables the send button while isAiTyping = true,
        // but this guard ensures correctness even if called programmatically.
        if (_uiState.value.isAiTyping) return

        val trimmed = _uiState.value.input.trim()

        // Issue 4: reject empty or oversized input
        if (trimmed.isEmpty() || trimmed.length > MAX_INPUT_LENGTH) return

        val userMessage = ChatMessage(
            id = nextId(),
            author = ChatAuthor.USER,
            text = trimmed,
        )
        val updatedMessages = _uiState.value.messages + userMessage
        _uiState.update {
            it.copy(messages = updatedMessages, input = "", isAiTyping = true)
        }

        viewModelScope.launch {
            val history = updatedMessages.dropLast(1)
            try {
                // Issue 2: fold callbacks both include isAiTyping = false so the
                // typing indicator is cleared in a single atomic state update
                repository.sendMessage(trimmed, history).fold(
                    onSuccess = { response ->
                        _uiState.update {
                            it.copy(
                                messages = it.messages + ChatMessage(
                                    id = nextId(),
                                    author = ChatAuthor.AI,
                                    text = response.response,
                                ),
                                isAiTyping = false,
                            )
                        }
                    },
                    onFailure = { exception ->
                        // Issue 5: inspect exception type to give the user
                        // a more actionable error message
                        _uiState.update {
                            it.copy(
                                messages = it.messages + ChatMessage(
                                    id = nextId(),
                                    author = ChatAuthor.AI,
                                    text = errorMessage(exception),
                                ),
                                isAiTyping = false,
                            )
                        }
                    },
                )
            } catch (e: CancellationException) {
                // Issue 2: if the coroutine is cancelled (e.g. user navigates away
                // and ViewModel is cleared), ensure the typing indicator is always
                // reset before re-throwing so the state is never left inconsistent
                _uiState.update { it.copy(isAiTyping = false) }
                throw e
            }
        }
    }

    fun clearChat() {
        _uiState.update {
            it.copy(
                messages = listOf(
                    ChatMessage(
                        id = nextId(),
                        author = ChatAuthor.AI,
                        text = "Chat cleared. What do you want help with?",
                    )
                ),
                isAiTyping = false,
            )
        }
    }

    // Issue 5: differentiate error types so the user knows whether to retry,
    // check their connection, or wait for the server
    private fun errorMessage(exception: Throwable): String = when (exception) {
        is SocketTimeoutException ->
            "Request timed out. The server may be busy — try again."
        is ConnectException, is IOException ->
            "Couldn't reach the server. Make sure it's running on your PC."
        else ->
            "Something went wrong. Please try again."
    }
}
