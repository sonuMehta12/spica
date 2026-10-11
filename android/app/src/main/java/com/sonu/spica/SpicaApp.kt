package com.sonu.spica

import android.app.Application
import coil3.ImageLoader
import coil3.PlatformContext
import coil3.SingletonImageLoader
import coil3.network.okhttp.OkHttpNetworkFetcherFactory
import okhttp3.OkHttpClient

/**
 * The app, and the one image loader every picture goes through. Wikimedia
 * asks each client to name itself, and a plan's pictures come from Commons
 * (`spec/in-progress/today-plan.md`), so every image request says who it is.
 */
class SpicaApp : Application(), SingletonImageLoader.Factory {
    override fun newImageLoader(context: PlatformContext): ImageLoader {
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                chain.proceed(chain.request().newBuilder().header("User-Agent", "Spica-Android/0.1 (personal use)").build())
            }
            .build()
        return ImageLoader.Builder(context)
            .components { add(OkHttpNetworkFetcherFactory(callFactory = { client })) }
            .build()
    }
}
