package com.example.videogamewizard.data.network

import retrofit2.http.Body
import retrofit2.http.POST

interface RagApi {
    @POST("chat")
    suspend fun chat(@Body request: ChatRequest): ChatResponse
}
