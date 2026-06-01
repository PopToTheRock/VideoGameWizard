package dev.alexn.videogamewizard

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dev.alexn.videogamewizard.navigation.AppNavGraph
import dev.alexn.videogamewizard.ui.theme.VideoGameWizardTheme

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
