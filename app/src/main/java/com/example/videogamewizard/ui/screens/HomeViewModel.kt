package com.example.videogamewizard.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.videogamewizard.data.model.ChatAuthor
import com.example.videogamewizard.data.model.ChatMessage
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class HomeViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    fun onInputChange(value: String) {
        _uiState.update { it.copy(input = value) }
    }

    fun sendMessage() {
        val trimmed = _uiState.value.input.trim()
        if (trimmed.isEmpty()) return

        _uiState.update {
            it.copy(
                messages = it.messages + ChatMessage(
                    id = System.currentTimeMillis(),
                    author = ChatAuthor.USER,
                    text = trimmed
                ),
                input = "",
                isAiTyping = true
            )
        }

        viewModelScope.launch {
            delay(600)
            _uiState.update {
                it.copy(
                    messages = it.messages + ChatMessage(
                        id = System.currentTimeMillis(),
                        author = ChatAuthor.AI,
                        text = "Got it. What platform (PC/PS/Xbox/Switch/mobile) and what's your goal (rank up, build optimization, walkthrough, etc.)?"
                    ),
                    isAiTyping = false
                )
            }
        }
    }

    fun clearChat() {
        _uiState.update {
            it.copy(
                messages = listOf(
                    ChatMessage(
                        id = System.currentTimeMillis(),
                        author = ChatAuthor.AI,
                        text = "Chat cleared. What do you want help with?"
                    )
                ),
                isAiTyping = false
            )
        }
    }
}
