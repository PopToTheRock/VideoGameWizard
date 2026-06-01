package dev.alexn.videogamewizard

import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.ComposeNavigator
import androidx.navigation.testing.TestNavHostController
import dev.alexn.videogamewizard.navigation.AppNavGraph
import dev.alexn.videogamewizard.navigation.Route
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test

class NavigationTest {
    @get:Rule
    val composeTestRule = createComposeRule()
    lateinit var navController: TestNavHostController

    @Before
    fun setupAppNavHost() {
        composeTestRule.setContent {
            navController = TestNavHostController(LocalContext.current)
            navController.navigatorProvider.addNavigator(ComposeNavigator())
            AppNavGraph(navController = navController)
        }
    }

    // Test navigation to the welcome screen (Initial screen)

    @Test
    fun appNavHost_verifyStartDestination() {
        composeTestRule
            .onNodeWithTag("welcome_screen")
            .assertIsDisplayed()
    }

    @Test
    fun appNavHost_verifyStartUI() {
        composeTestRule.onNodeWithText("Welcome to Video Game Wizard!").assertIsDisplayed()
    }

    @Test
    fun appNavHost_clickGetStarted_navigatesToHome() {
        composeTestRule
            .onNodeWithText("Get Started")
            .assertIsDisplayed()
            .performClick()

        composeTestRule
            .onNodeWithTag("home_screen")
            .assertIsDisplayed()

        composeTestRule.runOnIdle {
            assertTrue(navController.currentDestination?.hasRoute(Route.Home::class) == true)
        }
    }
}
