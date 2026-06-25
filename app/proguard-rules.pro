# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Preserve line numbers for readable release crash traces, but hide the original
# source file name so it isn't leaked in stack traces.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# ---------------------------------------------------------------------------
# kotlinx.serialization
# ---------------------------------------------------------------------------
# Recent kotlinx-serialization ships consumer rules in its artifact, but we keep
# these explicitly so a release build can never silently strip the generated
# serializers for our @Serializable models (which would throw SerializationException
# on the first network call). Rules per the official kotlinx.serialization guidance.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**

# Keep the Companion + serializer() of every @Serializable class.
-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
}
-if @kotlinx.serialization.Serializable class ** {
    static **$Companion Companion;
}
-keepclassmembers class <1>$Companion {
    kotlinx.serialization.KSerializer serializer(...);
}

# Belt-and-suspenders: keep our wire models and their generated $serializer.
-keep,includedescriptorclasses class dev.alexn.videogamewizard.data.network.**$$serializer { *; }
-keepclassmembers class dev.alexn.videogamewizard.data.network.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}

# ---------------------------------------------------------------------------
# Retrofit / OkHttp
# ---------------------------------------------------------------------------
# Retrofit and OkHttp bundle their own consumer R8 rules; this only adds the
# safety net of keeping our Retrofit service interface and its annotations.
-keep,allowobfuscation interface dev.alexn.videogamewizard.data.network.RagApi { *; }
-keepattributes Signature, Exceptions