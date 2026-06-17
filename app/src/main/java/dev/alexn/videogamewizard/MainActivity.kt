package dev.alexn.videogamewizard

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dev.alexn.videogamewizard.navigation.AppNavGraph
import dev.alexn.videogamewizard.ui.theme.VideoGameWizardTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Default edge-to-edge applies a near-opaque white scrim to the nav bar
        // in 3-button mode on a light theme, which hides the app's purple behind
        // it. Force a transparent nav bar with light icons to suit the dark
        // backdrop, so the bar blends into the screen in every navigation mode.
        enableEdgeToEdge(
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
        )
        setContent {
            VideoGameWizardTheme {
                AppNavGraph()
            }
        }
    }
}
