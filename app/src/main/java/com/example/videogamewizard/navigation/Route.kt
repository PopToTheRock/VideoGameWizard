package com.example.videogamewizard.navigation

import kotlinx.serialization.Serializable

sealed interface Route {
    @Serializable
    data object Welcome : Route

    @Serializable
    data object Home : Route
}
