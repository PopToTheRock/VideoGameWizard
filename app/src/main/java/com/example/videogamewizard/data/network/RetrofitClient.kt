package com.example.videogamewizard.data.network

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object RetrofitClient {

    /**
     * Base URL of the RAG server running on the developer's PC.
     *
     * Emulator → 10.0.2.2 maps to the host machine's localhost.
     * Physical device on the same WiFi → replace with the PC's local IP,
     * e.g. "http://192.168.1.42:8000/".
     */
    const val BASE_URL = "http://10.0.2.2:8000/"

    private val json = Json { ignoreUnknownKeys = true }

    private val okHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)  // LLM responses can take a while
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    val ragApi: RagApi = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(RagApi::class.java)
}
