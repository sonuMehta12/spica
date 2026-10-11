# kotlinx.serialization keeps its own serializers; the wire classes are
# annotated @Serializable and need their companions.
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class com.sonu.spica.** {
    *** Companion;
}
-keepclasseswithmembers class com.sonu.spica.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-dontwarn org.osmdroid.**
