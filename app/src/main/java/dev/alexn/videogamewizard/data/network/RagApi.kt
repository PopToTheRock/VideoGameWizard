package dev.alexn.videogamewizard.data.network

import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Streaming

interface RagApi {
    @POST("chat")
    suspend fun chat(
        @Body request: ChatRequest,
    ): ChatResponse

    /**
     * Streaming chat. [Streaming] keeps Retrofit from buffering the whole body,
     * so the raw [ResponseBody] can be read line-by-line as NDJSON events arrive.
     */
    @Streaming
    @POST("chat/stream")
    suspend fun chatStream(
        @Body request: ChatRequest,
    ): ResponseBody

    @POST("feedback")
    suspend fun sendFeedback(
        @Body request: FeedbackRequest,
    ): FeedbackResponse
}
