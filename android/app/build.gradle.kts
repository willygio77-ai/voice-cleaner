plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.voicecleaner"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.voicecleaner"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        viewBinding = true
    }
    // Impedisce la compressione dei modelli TFLite per consentire il memory mapping rapido
    androidResources {
        noCompress.add("tflite")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.activity:activity-ktx:1.9.0")
    
    // Coroutine per elaborazione audio asincrona in background
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    
    // TensorFlow Lite Runtime ufficiale per l'inferenza del modello DTLN offline
    implementation("org.tensorflow:tensorflow-lite:2.14.0")
}
