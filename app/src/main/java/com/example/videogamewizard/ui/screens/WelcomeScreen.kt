package com.example.videogamewizard.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.videogamewizard.ui.theme.Purple40
import com.example.videogamewizard.ui.theme.PurpleGrey40
import com.example.videogamewizard.ui.theme.PurpleGrey80

@Composable
fun WelcomeScreen(onGetStarted: () -> Unit) {
    Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .testTag("welcome_screen")
                .background(color = Purple40)
                .padding(innerPadding)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .wrapContentSize(Alignment.Center)
            ) {
                Box(
                    modifier = Modifier
                        .border(
                            width = 4.dp,
                            color = PurpleGrey40,
                            shape = RoundedCornerShape(16.dp)
                        )
                        .background(
                            shape = RoundedCornerShape(16.dp),
                            color = PurpleGrey80
                        )
                        .padding(16.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Welcome to Video Game Wizard!",
                        color = Color.DarkGray
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = { onGetStarted() },
                    modifier = Modifier
                        .width(200.dp)
                        .height(50.dp)
                        .align(alignment = Alignment.CenterHorizontally)
                ) {
                    Text(
                        text = "Get Started",
                        color = Color.White
                    )
                }
            }
        }
    }
}
