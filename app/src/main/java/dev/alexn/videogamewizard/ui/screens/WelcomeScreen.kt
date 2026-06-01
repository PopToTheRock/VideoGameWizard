package dev.alexn.videogamewizard.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.alexn.videogamewizard.R
import dev.alexn.videogamewizard.ui.theme.Purple40
import dev.alexn.videogamewizard.ui.theme.PurpleGrey40
import dev.alexn.videogamewizard.ui.theme.PurpleGrey80

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
                        text = stringResource(R.string.welcome_title),
                        color = Color.DarkGray
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                // No fixed width/height: the button sizes to its content plus
                // padding so it scales with the user's font-size preference
                // (a hard-coded height clips large accessibility text).
                Button(
                    onClick = { onGetStarted() },
                    modifier = Modifier
                        .align(alignment = Alignment.CenterHorizontally)
                        .padding(horizontal = 32.dp)
                ) {
                    Text(
                        text = stringResource(R.string.welcome_get_started),
                        color = Color.White
                    )
                }
            }
        }
    }
}
