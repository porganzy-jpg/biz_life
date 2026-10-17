plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "app.goyo.detox"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.goyo.detox"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-p0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

// 외부 라이브러리 없음: JSON은 android 내장 org.json, UI는 기본 View.
// INTERNET 권한도 없음 — 화면 내용은 기기 밖으로 나가지 않는다.
dependencies {}
