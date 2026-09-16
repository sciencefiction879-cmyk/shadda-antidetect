package com.shadda.antidetect;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.webkit.ConsoleMessage;
import android.webkit.DownloadListener;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.webkit.ProxyConfig;
import androidx.webkit.ProxyController;
import androidx.webkit.WebViewFeature;

import java.util.concurrent.Executors;

public class BrowserActivity extends Activity {
    private WebView webView;
    private TextView tvUrl;
    private String profileName = "Default Profile";
    private String proxyLabel = "Direct";
    private String userAgent = "";
    private String proxyUrl = "";
    private String startUrl = "https://www.google.com";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);

        if (getIntent() != null) {
            String pName = getIntent().getStringExtra("profileName");
            if (!TextUtils.isEmpty(pName)) profileName = pName;

            String pLabel = getIntent().getStringExtra("proxyLabel");
            if (!TextUtils.isEmpty(pLabel)) proxyLabel = pLabel;

            String ua = getIntent().getStringExtra("userAgent");
            if (!TextUtils.isEmpty(ua)) userAgent = ua;

            String pUrl = getIntent().getStringExtra("proxyUrl");
            if (!TextUtils.isEmpty(pUrl)) proxyUrl = pUrl;

            String sUrl = getIntent().getStringExtra("startUrl");
            if (!TextUtils.isEmpty(sUrl)) startUrl = sUrl;
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#080c14"));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setBackgroundColor(Color.parseColor("#0f172a"));
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(8), dp(6), dp(8), dp(6));

        Button btnBack = createNavButton("◀");
        btnBack.setOnClickListener(v -> {
            if (webView != null && webView.canGoBack()) {
                webView.goBack();
            } else {
                finish();
            }
        });
        toolbar.addView(btnBack);

        Button btnForward = createNavButton("▶");
        btnForward.setOnClickListener(v -> {
            if (webView != null && webView.canGoForward()) {
                webView.goForward();
            }
        });
        toolbar.addView(btnForward);

        Button btnRefresh = createNavButton("🔄");
        btnRefresh.setOnClickListener(v -> {
            if (webView != null) webView.reload();
        });
        toolbar.addView(btnRefresh);

        LinearLayout pill = new LinearLayout(this);
        pill.setOrientation(LinearLayout.HORIZONTAL);
        pill.setGravity(Gravity.CENTER_VERTICAL);
        GradientDrawable pillBg = new GradientDrawable();
        pillBg.setColor(Color.parseColor("#1e293b"));
        pillBg.setCornerRadius(dp(16));
        pillBg.setStroke(dp(1), Color.parseColor("#38bdf8"));
        pill.setBackground(pillBg);
        pill.setPadding(dp(10), dp(4), dp(10), dp(4));

        LinearLayout.LayoutParams pillParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f);
        pillParams.setMargins(dp(6), 0, dp(6), 0);
        pill.setLayoutParams(pillParams);

        TextView tvTitle = new TextView(this);
        tvTitle.setText("👤 " + profileName + " (" + proxyLabel + ")");
        tvTitle.setTextColor(Color.parseColor("#38bdf8"));
        tvTitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        tvTitle.setTypeface(Typeface.DEFAULT_BOLD);
        tvTitle.setSingleLine(true);
        tvTitle.setEllipsize(TextUtils.TruncateAt.END);
        pill.addView(tvTitle);

        toolbar.addView(pill);

        Button btnClose = createNavButton("✕");
        btnClose.setOnClickListener(v -> finish());
        toolbar.addView(btnClose);

        root.addView(toolbar, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(48)));

        tvUrl = new TextView(this);
        tvUrl.setText(startUrl);
        tvUrl.setTextColor(Color.parseColor("#94a3b8"));
        tvUrl.setBackgroundColor(Color.parseColor("#090d16"));
        tvUrl.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        tvUrl.setPadding(dp(10), dp(2), dp(10), dp(2));
        tvUrl.setSingleLine(true);
        tvUrl.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        root.addView(tvUrl, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(22)));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#080c14"));
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setSupportZoom(true);
        ws.setBuiltInZoomControls(true);
        ws.setDisplayZoomControls(false);

        if (!TextUtils.isEmpty(userAgent)) {
            ws.setUserAgentString(userAgent);
        }

        configureProxy(proxyUrl);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                view.loadUrl(url);
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                if (tvUrl != null) {
                    tvUrl.setText(url);
                }
                injectProfileBadge(view);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage consoleMessage) {
                return super.onConsoleMessage(consoleMessage);
            }
        });

        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimeType, long contentLength) {
                try {
                    DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                    req.setMimeType(mimeType);
                    req.addRequestHeader("User-Agent", userAgent);
                    req.setDescription("Downloading file...");
                    req.setTitle(URLUtil_guessFileName(url, contentDisposition, mimeType));
                    req.allowScanningByMediaScanner();
                    req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, URLUtil_guessFileName(url, contentDisposition, mimeType));

                    DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                    if (dm != null) {
                        dm.enqueue(req);
                        Toast.makeText(BrowserActivity.this, "📥 Downloading: " + URLUtil_guessFileName(url, contentDisposition, mimeType), Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    Toast.makeText(BrowserActivity.this, "Download failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            }
        });

        root.addView(webView, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));

        setContentView(root);

        webView.loadUrl(startUrl);
    }

    private Button createNavButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextColor(Color.parseColor("#f8fafc"));
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        b.setBackgroundColor(Color.TRANSPARENT);
        b.setPadding(dp(4), dp(2), dp(4), dp(2));
        b.setMinWidth(dp(36));
        b.setMinimumWidth(dp(36));
        return b;
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    private void configureProxy(String rawProxy) {
        if (TextUtils.isEmpty(rawProxy)) return;
        try {
            if (WebViewFeature.isFeatureSupported(WebViewFeature.PROXY_OVERRIDE)) {
                ProxyConfig.Builder builder = new ProxyConfig.Builder();
                String cleanProxy = rawProxy.trim();
                builder.addProxyRule(cleanProxy);
                ProxyController.getInstance().setProxyOverride(builder.build(), Executors.newSingleThreadExecutor(), () -> {
                });
            }
        } catch (Exception e) {
        }
    }

    private void injectProfileBadge(WebView view) {
        String safeName = profileName.replace("'", "\\'").replace("\"", "\\\"");
        String safeProxy = proxyLabel.replace("'", "\\'").replace("\"", "\\\"");
        String script = "javascript:(function() {" +
                "window.__SHADDA_PROFILE_NAME__ = '" + safeName + "';" +
                "window.__SHADDA_PROXY_LABEL__ = '" + safeProxy + "';" +
                "if (document.getElementById('shadda-mobile-badge')) return;" +
                "var b = document.createElement('div');" +
                "b.id = 'shadda-mobile-badge';" +
                "b.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:2147483647;background:rgba(15,23,42,0.92);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.5);border-radius:20px;padding:6px 12px;display:flex;align-items:center;gap:6px;box-shadow:0 4px 12px rgba(0,0,0,0.5);font-family:system-ui,-apple-system,sans-serif;pointer-events:auto;user-select:none;font-size:12px;color:#38bdf8;font-weight:700;';" +
                "b.innerHTML = '<span>👤 " + safeName + "</span><span style=\"color:#94a3b8;font-size:11px;\">• " + safeProxy + "</span>';" +
                "document.body.appendChild(b);" +
                "})();";
        view.evaluateJavascript(script, null);
    }

    private String URLUtil_guessFileName(String url, String contentDisposition, String mimeType) {
        try {
            return android.webkit.URLUtil.guessFileName(url, contentDisposition, mimeType);
        } catch (Exception e) {
            return "downloaded_file";
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

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        super.onDestroy();
    }
}
