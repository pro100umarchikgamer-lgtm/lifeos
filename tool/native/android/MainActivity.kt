package app.lifeos.lifeos

import android.app.*
import android.content.*
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.*
import java.time.ZoneId

class MainActivity : FlutterActivity() {
    private var documentResult: MethodChannel.Result? = null
    private var backupBytes: ByteArray? = null
    private var launchId: String? = null
    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        launchId = intent?.data?.lastPathSegment
        MethodChannel(engine.dartExecutor.binaryMessenger, "lifeos/native").setMethodCallHandler { call, result ->
            try {
                when (call.method) {
                    "wallpaperSeed" -> {
                        val id = if (Build.VERSION.SDK_INT >= 31) resources.getIdentifier("system_accent1_600", "color", "android") else 0
                        result.success(if (id != 0) resources.getColor(id, theme).toLong() and 0xffffffffL else null)
                    }
                    "diagnostics" -> {
                        ReminderRuntime.channels(this, if (call.arguments is Map<*, *>) JSONObject(call.arguments as Map<*, *>) else null)
                        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                        val enabled = if (Build.VERSION.SDK_INT >= 24) manager.areNotificationsEnabled() else true
                        val permission = Build.VERSION.SDK_INT < 33 || checkSelfPermission("android.permission.POST_NOTIFICATIONS") == PackageManager.PERMISSION_GRANTED
                        result.success(mapOf("supported" to true, "zone" to ZoneId.systemDefault().id,
                            "entriesCount" to ReminderRuntime.read(this).getJSONArray("entries").length(),
                            "enabled" to (enabled && permission), "exact" to ReminderRuntime.exact(this),
                            "channels" to if (Build.VERSION.SDK_INT >= 26) listOf("standard", "important", "alarm").associateWith { name ->
                                val channel = manager.getNotificationChannel("lifeos.$name")
                                mapOf("importance" to channel.importance, "sound" to (channel.sound != null))
                            } else emptyMap<String, Any>()))
                    }
                    "reconcile" -> { ReminderRuntime.reconcile(this, JSONArray(call.argument<List<Any>>("entries"))); result.success(null) }
                    "pendingActions" -> result.success(convert(ReminderRuntime.read(this).getJSONArray("actions")))
                    "ackActions" -> { ReminderRuntime.acknowledge(this, (call.arguments as List<*>).map { it as String }.toSet()); result.success(null) }
                    "launchTarget" -> { result.success(launchId); launchId = null }
                    "requestNotifications" -> {
                        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 73)
                        else startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName))
                        result.success(null)
                    }
                    "requestExactAlarms" -> {
                        if (Build.VERSION.SDK_INT >= 31) startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM, Uri.parse("package:$packageName")))
                        result.success(null)
                    }
                    "notificationSettings" -> { startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, packageName)); result.success(null) }
                    "testNotification" -> {
                        val e = JSONObject(call.arguments as Map<*, *>).put("id", "test").put("revision", 1)
                            .put("schedule", JSONObject().put("mode", "standard"))
                        ReminderRuntime.show(this, e, System.currentTimeMillis()); result.success(null)
                    }
                    "saveBackup", "readBackup", "pickStatement" -> {
                        check(documentResult == null) { "Document operation already in progress" }
                        documentResult = result
                        if (call.method == "saveBackup") {
                            backupBytes = call.arguments as ByteArray
                            require(backupBytes!!.size <= 20 * 1024 * 1024)
                            startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                                .setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE, "LifeOS.lifeosbackup"), 81)
                        } else startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"), if (call.method == "pickStatement") 83 else 82)
                    }
                    else -> result.notImplemented()
                }
            } catch (e: Exception) {
                if (documentResult === result) { documentResult = null; backupBytes = null }
                result.error("native_failed", e.javaClass.simpleName, null)
            }
        }
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); launchId = intent.data?.lastPathSegment }
    @Deprecated("Platform compatibility callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode !in 81..83) return
        val result = documentResult ?: return
        documentResult = null
        try {
            val uri = data?.data
            if (resultCode != Activity.RESULT_OK || uri == null) { result.success(if (requestCode == 81) false else null); return }
            if (requestCode == 81) {
                contentResolver.openOutputStream(uri, "wt")!!.use { it.write(backupBytes!!) }
                val saved = readDocument(uri)
                check(java.security.MessageDigest.isEqual(saved, backupBytes!!))
                result.success(true)
            } else if (requestCode == 83) {
                // User granted only this URI. Do not retain URI permission or copy source into app files.
                Thread {
                    try {
                        var name = ""
                        contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                            if (cursor.moveToFirst()) name = cursor.getString(0)
                        }
                        val bytes = readDocument(uri, 5 * 1024 * 1024)
                        val value = if (name.endsWith(".xlsx", true)) mapOf("name" to name, "sheets" to StatementReader.sheets(bytes)) else if (name.endsWith(".xml", true)) mapOf("name" to name, "sheets" to StatementReader.statementXml(bytes)) else mapOf("name" to name, "bytes" to bytes)
                        runOnUiThread { result.success(value); bytes.fill(0) }
                    } catch (e: Exception) { runOnUiThread { result.error("statement_failed", e.javaClass.simpleName, null) } }
                }.start()
            } else {
                result.success(readDocument(uri))
            }
        } catch (e: Exception) { result.error("document_failed", e.javaClass.simpleName, null) }
        finally { backupBytes = null }
    }
    private fun readDocument(uri: Uri, limit: Int = 20 * 1024 * 1024): ByteArray {
        val output = java.io.ByteArrayOutputStream()
        contentResolver.openInputStream(uri)!!.use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val n = input.read(buffer); if (n < 0) break
                require(output.size() + n <= limit)
                output.write(buffer, 0, n)
            }
        }
        return output.toByteArray()
    }
    private fun convert(value: Any?): Any? = when (value) {
        JSONObject.NULL -> null
        is JSONObject -> value.keys().asSequence().associateWith { convert(value.get(it)) }
        is JSONArray -> (0 until value.length()).map { convert(value.get(it)) }
        else -> value
    }
}
