package dev.alexn.videogamewizard

import android.app.Application
import dev.alexn.videogamewizard.di.AppContainer
import dev.alexn.videogamewizard.di.DefaultAppContainer

/** Application entry point. Builds the manual-DI [AppContainer] once at startup. */
class VideoGameWizardApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = DefaultAppContainer(this)
    }
}
