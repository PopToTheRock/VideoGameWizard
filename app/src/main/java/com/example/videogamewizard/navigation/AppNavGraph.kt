package com.example.videogamewizard.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.videogamewizard.ui.screens.HomeScreen
import com.example.videogamewizard.ui.screens.WelcomeScreen

@Composable
fun AppNavGraph(navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = Route.Welcome) {
        composable<Route.Welcome> {
            WelcomeScreen(onGetStarted = { navController.navigate(Route.Home) })
        }
        composable<Route.Home> {
            HomeScreen(onBack = { navController.navigateUp() })
        }
    }
}
