package dev.alexn.videogamewizard.data.network

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dev.alexn.videogamewizard.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object RetrofitClient {
    // Quick to fail on a dead connection, but generous on the read: LLM
    // generation routinely takes tens of seconds for a full response.
    private const val CONNECT_TIMEOUT_SECONDS = 10L
    private const val READ_TIMEOUT_SECONDS = 120L
    private const val WRITE_TIMEOUT_SECONDS = 10L

    private val json = Json { ignoreUnknownKeys = true }

    private val okHttpClient =
        OkHttpClient
            .Builder()
            .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .writeTimeout(WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
            .build()

    val ragApi: RagApi =
        Retrofit
            .Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(RagApi::class.java)
}
