package com.example.videogamewizard

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.example.videogamewizard.navigation.AppNavGraph
import com.example.videogamewizard.ui.theme.VideoGameWizardTheme

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
