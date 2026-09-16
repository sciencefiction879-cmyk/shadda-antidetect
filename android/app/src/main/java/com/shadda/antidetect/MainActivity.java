package com.shadda.antidetect;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.view.Window;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private WebView webView;
    private static final String PREF_NAME = "shadda_antidetect_db";
    private static final String KEY_PROFILES = "profiles_json";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);

        webView = new WebView(this);
        webView.setBackgroundColor(0xFF080C14);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        // Attach Android Native Bridge
        webView.addJavascriptInterface(new AndroidBridge(this), "AndroidBridge");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                view.loadUrl(url);
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                view.evaluateJavascript("window.isAndroidApp = true;", null);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage consoleMessage) {
                return super.onConsoleMessage(consoleMessage);
            }
        });

        webView.loadUrl("file:///android_asset/static/index.html");
    }

    public class AndroidBridge {
        private final Context context;

        public AndroidBridge(Context context) {
            this.context = context;
        }

        @JavascriptInterface
        public boolean isAndroidApp() {
            return true;
        }

        @JavascriptInterface
        public String getProfiles() {
            SharedPreferences prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
            String saved = prefs.getString(KEY_PROFILES, "");
            if (!TextUtils.isEmpty(saved) && !saved.equals("[]")) {
                return saved;
            }
            // Return default seed profiles
            return "[" +
                    "{\"id\":\"profile_1\",\"name\":\"YouTube Studio Profile\",\"proxyType\":\"none\",\"assignedProxyId\":\"\",\"assignedProxyLabel\":\"Direct\",\"color\":\"#0ea5e9\",\"startUrl\":\"https://studio.youtube.com\",\"userAgentId\":\"samsung_s24\",\"userAgent\":\"Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36\",\"isMobile\":true,\"createdAt\":\"2026-09-16\"}," +
                    "{\"id\":\"profile_2\",\"name\":\"YouTube Retention Watcher\",\"proxyType\":\"country\",\"assignedProxyId\":\"proxy_7\",\"assignedProxyNumber\":7,\"assignedProxyLabel\":\"Proxy #7\",\"countryProxy\":\"socks5://72.195.34.35:27360\",\"color\":\"#ec4899\",\"startUrl\":\"https://www.youtube.com\",\"userAgentId\":\"pixel_9_pro\",\"userAgent\":\"Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36\",\"isMobile\":true,\"createdAt\":\"2026-09-16\"}" +
                    "]";
        }

        @JavascriptInterface
        public boolean saveProfiles(String json) {
            try {
                SharedPreferences prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
                prefs.edit().putString(KEY_PROFILES, json).apply();
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public String getProxiesPool() {
            try {
                InputStream is = context.getAssets().open("proxies_pool.json");
                int size = is.available();
                byte[] buffer = new byte[size];
                is.read(buffer);
                is.close();
                return new String(buffer, StandardCharsets.UTF_8);
            } catch (Exception e) {
                return "[]";
            }
        }

        @JavascriptInterface
        public void launchProfile(String profileJson) {
            try {
                JSONObject obj = new JSONObject(profileJson);
                String name = obj.optString("name", "Android Profile");
                String startUrl = obj.optString("startUrl", "https://studio.youtube.com");
                String ua = obj.optString("userAgent", "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36");
                String proxyLabel = obj.optString("assignedProxyLabel", "Direct");
                String proxyUrl = obj.optString("countryProxy", "");
                if (TextUtils.isEmpty(proxyUrl)) {
                    proxyUrl = obj.optString("customProxy", "");
                }

                Intent intent = new Intent(MainActivity.this, BrowserActivity.class);
                intent.putExtra("profileName", name);
                intent.putExtra("startUrl", startUrl);
                intent.putExtra("userAgent", ua);
                intent.putExtra("proxyLabel", proxyLabel);
                intent.putExtra("proxyUrl", proxyUrl);
                startActivity(intent);
            } catch (Exception e) {
                Toast.makeText(MainActivity.this, "Launch failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
            }
        }

        @JavascriptInterface
        public void showToast(String message) {
            Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
