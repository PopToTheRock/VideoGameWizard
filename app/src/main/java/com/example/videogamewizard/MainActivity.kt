package com.example.videogamewizard

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.videogamewizard.ui.theme.VideoGameWizardTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VideoGameWizardTheme {
                TestScreen()
            }
        }
    }
}

@Composable
fun TestScreen() {
    Scaffold(modifier = Modifier
        .fillMaxSize()) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .wrapContentSize(Alignment.Center)
        ) {
            Box(modifier = Modifier
                .size(300.dp)
                .border(
                    width = 4.dp,
                    color = Color.Black,
                    shape = RoundedCornerShape(16.dp)
                ).background(
                    shape = RoundedCornerShape(16.dp),
                    color = Color.Gray
                ),
                contentAlignment = Alignment.Center) {
                Text(
                    text = "Deez Nuts",
                    color = Color.Cyan
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun TestPreview() {
    VideoGameWizardTheme {
        TestScreen()
    }
}