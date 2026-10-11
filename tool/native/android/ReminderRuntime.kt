package app.lifeos.lifeos

import android.app.*
import android.content.*
import android.content.pm.PackageManager
import android.media.*
import android.net.Uri
import android.os.*
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.*
import java.security.KeyStore
import java.time.*
import java.time.temporal.ChronoUnit
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Scheduling metadata and action outbox are encrypted independently of SQLCipher. */
object ReminderRuntime {
    private const val ALIAS = "lifeos.reminders.v1"
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (store.containsAlias(ALIAS)) return store.getKey(ALIAS, null) as SecretKey
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }
    fun read(c: Context): JSONObject {
        val encoded = c.getSharedPreferences("reminders", 0).getString("encrypted", null) ?: return JSONObject().put("entries", JSONArray()).put("actions", JSONArray())
        val bytes = Base64.decode(encoded, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
        return JSONObject(String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8))
    }
    private fun write(c: Context, state: JSONObject) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val bytes = cipher.iv + cipher.doFinal(state.toString().toByteArray(Charsets.UTF_8))
        check(c.getSharedPreferences("reminders", 0).edit().putString("encrypted", Base64.encodeToString(bytes, Base64.NO_WRAP)).commit())
    }
    private fun alarm(c: Context) = c.getSystemService(Context.ALARM_SERVICE) as AlarmManager
    private fun notifications(c: Context) = c.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    private fun intent(c: Context, id: String, slot: String, epoch: Long, revision: Int) = Intent(c, ReminderReceiver::class.java)
        .setAction("lifeos.fire").setData(Uri.parse("lifeos://reminder/$id/$slot"))
        .putExtra("id", id).putExtra("slot", slot).putExtra("epoch", epoch).putExtra("revision", revision)
    private fun pending(c: Context, id: String, slot: String, epoch: Long, revision: Int) = PendingIntent.getBroadcast(c, 0,
        intent(c, id, slot, epoch, revision), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    fun exact(c: Context): Boolean = Build.VERSION.SDK_INT < 31 || alarm(c).canScheduleExactAlarms()
    fun channels(c: Context) {
        if (Build.VERSION.SDK_INT < 26) return
        for ((id, priority) in listOf("standard" to NotificationManager.IMPORTANCE_DEFAULT, "important" to NotificationManager.IMPORTANCE_HIGH, "alarm" to NotificationManager.IMPORTANCE_HIGH)) {
            notifications(c).createNotificationChannel(NotificationChannel("lifeos.$id", "LifeOS · $id", priority).apply {
                enableVibration(id != "standard")
                if (id == "alarm") setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM), AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build())
            })
        }
    }
    fun canAlert(c: Context, mode: String): Boolean {
        if (Build.VERSION.SDK_INT >= 33 && c.checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) return false
        if (Build.VERSION.SDK_INT >= 24 && !notifications(c).areNotificationsEnabled()) return false
        return Build.VERSION.SDK_INT < 26 || notifications(c).getNotificationChannel("lifeos.$mode").importance > 0
    }
    fun canSound(c: Context): Boolean = canAlert(c,"alarm") &&
        (Build.VERSION.SDK_INT < 26 || notifications(c).getNotificationChannel("lifeos.alarm").sound != null)
    fun canVibrate(c: Context): Boolean = canAlert(c,"alarm") &&
        (Build.VERSION.SDK_INT < 26 || notifications(c).getNotificationChannel("lifeos.alarm").shouldVibrate())
    private fun schedule(c: Context, entry: JSONObject, slot: String, at: Long, epoch: Long) {
        if (at <= System.currentTimeMillis()) return
        val p = pending(c, entry.getString("id"), slot, epoch, entry.getInt("revision"))
        val mode = entry.getJSONObject("schedule").getString("mode")
        try {
            if (mode == "alarm" && exact(c)) {
                alarm(c).setAlarmClock(AlarmManager.AlarmClockInfo(at, open(c, entry.getString("id"))), p)
            } else if (mode == "important" && exact(c)) {
                alarm(c).setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p)
            } else alarm(c).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p)
        } catch (_: SecurityException) {
            alarm(c).setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p)
        }
    }
    private fun cancel(c: Context, e: JSONObject) {
        val id = e.getString("id")
        alarm(c).cancel(pending(c, id, "regular", 0, 0))
        val snoozes = e.optJSONArray("snoozes") ?: JSONArray()
        for (i in 0 until snoozes.length()) alarm(c).cancel(pending(c, id, "s${snoozes.getJSONObject(i).getLong("epoch")}", 0, 0))
        notifications(c).cancel(id, 1)
    }
    @Synchronized fun reconcile(c: Context, entries: JSONArray) {
        channels(c)
        val state = read(c)
        val old = state.getJSONArray("entries")
        for (i in 0 until old.length()) cancel(c, old.getJSONObject(i))
        for (i in 0 until entries.length()) {
            val e = entries.getJSONObject(i)
            val previous = entry(state,e.getString("id"))
            if (previous != null && previous.getInt("revision") == e.getInt("revision")) e.put("lastFired",previous.optLong("lastFired",0))
        }
        // Persist before scheduling: reboot recovery can reconstruct any interrupted reconciliation.
        state.put("entries", entries)
        val active = AlarmService.activeId?.let { entry(state, it) }
        if (AlarmService.activeId != null) {
            if (active == null || active.getInt("revision") != AlarmService.activeRevision || active.getJSONObject("schedule").getString("mode") != "alarm") {
                c.stopService(Intent(c, AlarmService::class.java))
            } else notifications(c).notify(9001, notification(c, active, AlarmService.activeEpoch))
        }
        write(c, state)
        recovery(c)
    }
    @Synchronized fun recovery(c: Context, recalculate: Boolean = false) {
        val state = read(c)
        val entries = state.getJSONArray("entries")
        for (i in 0 until entries.length()) {
            val e = entries.getJSONObject(i)
            var scheduledAt = e.optLong("nextAt", 0)
            val after = maxOf(System.currentTimeMillis(), e.optLong("lastFired",0))
            if (recalculate || scheduledAt <= after) scheduledAt = next(e, after) ?: 0
            e.put("nextAt", scheduledAt)
            if (scheduledAt > 0) schedule(c, e, "regular", scheduledAt, scheduledAt)
            val snoozes = e.optJSONArray("snoozes") ?: JSONArray()
            for (j in 0 until snoozes.length()) {
                val s = snoozes.getJSONObject(j)
                schedule(c, e, "s${s.getLong("epoch")}", s.getLong("until"), s.getLong("epoch"))
            }
        }
        write(c, state)
    }
    /** The same anchored wall-clock recurrence and end-of-month clamp as the Dart engine. */
    fun next(e: JSONObject, after: Long): Long? {
        val spec = e.getJSONObject("schedule")
        val start = LocalDateTime.parse(spec.getString("localStart"))
        val zone = if (spec.getString("timezone") == "device") ZoneId.systemDefault() else ZoneId.of(spec.getString("timezone"))
        val rule = spec.getString("repeat")
        val interval = spec.getInt("interval").toLong()
        val from = Instant.ofEpochMilli(after).atZone(zone).toLocalDate()
        val days = ChronoUnit.DAYS.between(start.toLocalDate(), from)
        var n = when (rule) {
            "daily" -> days / interval - 1
            "weekly" -> days / (interval * 7) - 1
            "monthly" -> ((from.year - start.year) * 12L + from.monthValue - start.monthValue) / interval - 1
            "yearly" -> (from.year - start.year) / interval - 1
            else -> 0
        }.coerceAtLeast(0)
        repeat(5000) {
            val local = when (rule) {
                "daily" -> start.plusDays(n * interval)
                "weekly" -> start.plusWeeks(n * interval)
                "monthly" -> start.plusMonths(n * interval)
                "yearly" -> start.plusYears(n * interval)
                else -> start
            }
            val end = spec.optString("until", "")
            if (local.year > 2200 || (end.isNotEmpty() && end != "null" && local.toLocalDate().toString() > end)) return null
            val at = local.atZone(zone).toInstant().toEpochMilli()
            if (at > after) return at
            if (rule == "none") return null
            n++
        }
        return null
    }
    private fun entry(state: JSONObject, id: String): JSONObject? {
        val entries = state.getJSONArray("entries")
        for (i in 0 until entries.length()) if (entries.getJSONObject(i).getString("id") == id) return entries.getJSONObject(i)
        return null
    }
    @Synchronized fun fire(c: Context, input: Intent) {
        val state = read(c)
        val e = entry(state, input.getStringExtra("id") ?: "") ?: return
        if (e.getInt("revision") != input.getIntExtra("revision", -1)) return
        val epoch = input.getLongExtra("epoch", 0)
        val regular = input.getStringExtra("slot") == "regular"
        if (regular) {
            if (e.optLong("nextAt", 0) != epoch) return
            e.put("lastFired",epoch)
            e.put("nextAt", next(e, maxOf(System.currentTimeMillis(),epoch)))
            write(c, state)
            val at = e.optLong("nextAt", 0)
            if (at > 0) schedule(c, e, "regular", at, at)
        }
        if (!regular) {
            val snoozes = e.optJSONArray("snoozes") ?: JSONArray()
            if (!(0 until snoozes.length()).any { snoozes.getJSONObject(it).getLong("epoch") == epoch }) return
            val remaining = JSONArray()
            for (i in 0 until snoozes.length()) if (snoozes.getJSONObject(i).getLong("epoch") != epoch) remaining.put(snoozes.getJSONObject(i))
            e.put("snoozes", remaining); write(c, state)
        }
        show(c, e, epoch)
        if (e.getJSONObject("schedule").getString("mode") == "alarm" && (canSound(c) || canVibrate(c))) {
            try {
                val service = Intent(c, AlarmService::class.java).putExtra("entry", e.toString()).putExtra("epoch", epoch)
                if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(service) else c.startService(service)
            } catch (_: RuntimeException) { /* Notification remains available when foreground launch is restricted. */ }
        }
    }
    private fun open(c: Context, id: String): PendingIntent = PendingIntent.getActivity(c, 0,
        Intent(c, MainActivity::class.java).setData(Uri.parse("lifeos://calendar/$id")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    private fun action(c: Context, e: JSONObject, epoch: Long, status: String): PendingIntent = PendingIntent.getBroadcast(c, 0,
        Intent(c, ReminderReceiver::class.java).setAction("lifeos.$status").setData(Uri.parse("lifeos://action/${e.getString("id")}/$epoch/$status"))
            .putExtra("id", e.getString("id")).putExtra("epoch", epoch).putExtra("revision", e.getInt("revision")),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    fun notification(c: Context, e: JSONObject, epoch: Long): Notification {
        val mode = e.getJSONObject("schedule").getString("mode")
        val builder = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(c, "lifeos.$mode") else Notification.Builder(c)
        return builder.setSmallIcon(android.R.drawable.ic_lock_idle_alarm).setContentTitle(e.getString("title"))
            .setContentText(e.getString("message")).setContentIntent(open(c, e.getString("id"))).setAutoCancel(false)
            .setCategory(if (mode == "alarm") Notification.CATEGORY_ALARM else Notification.CATEGORY_REMINDER)
            .setPriority(if (mode == "standard") Notification.PRIORITY_DEFAULT else Notification.PRIORITY_HIGH)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(Notification.Action.Builder(null, e.getString("doneLabel"), action(c, e, epoch, "completed")).build())
            .addAction(Notification.Action.Builder(null, e.getString("snoozeLabel"), action(c, e, epoch, "snoozed")).build())
            .addAction(Notification.Action.Builder(null, e.getString("dismissLabel"), action(c, e, epoch, "dismissed")).build())
            .setDeleteIntent(action(c, e, epoch, "dismissed")).build()
    }
    fun show(c: Context, e: JSONObject, epoch: Long) {
        channels(c)
        try { notifications(c).notify(e.getString("id"), 1, notification(c, e, epoch)) } catch (_: SecurityException) { }
    }
    @Synchronized fun act(c: Context, input: Intent) {
        val state = read(c)
        val id = input.getStringExtra("id") ?: return
        val e = entry(state, id) ?: return
        if (e.getInt("revision") != input.getIntExtra("revision", -1)) return
        val epoch = input.getLongExtra("epoch", 0)
        val status = input.action!!.substringAfter("lifeos.")
        val change = JSONObject().put("id", UUID.randomUUID().toString()).put("entryId", id).put("epoch", epoch).put("status", status).put("revision", e.getInt("revision"))
        val snoozes = e.optJSONArray("snoozes") ?: JSONArray()
        val remaining = JSONArray()
        for (i in 0 until snoozes.length()) if (snoozes.getJSONObject(i).getLong("epoch") != epoch) remaining.put(snoozes.getJSONObject(i))
        alarm(c).cancel(pending(c, id, "s$epoch", 0, 0))
        if (status == "snoozed") {
            val until = System.currentTimeMillis() + e.getInt("snoozeMinutes") * 60000L
            change.put("snoozedUntil", until)
            remaining.put(JSONObject().put("epoch", epoch).put("until", until))
        }
        e.put("snoozes", remaining)
        state.getJSONArray("actions").put(change)
        write(c, state) // Do not dismiss an alert until its durable action has been written.
        notifications(c).cancel(id, 1)
        if (AlarmService.activeId == id && AlarmService.activeEpoch == epoch) c.stopService(Intent(c, AlarmService::class.java))
        recovery(c)
    }
    @Synchronized fun acknowledge(c: Context, ids: Set<String>) {
        val state = read(c)
        val actions = state.getJSONArray("actions")
        val remaining = JSONArray()
        for (i in 0 until actions.length()) if (!ids.contains(actions.getJSONObject(i).getString("id"))) remaining.put(actions.getJSONObject(i))
        state.put("actions", remaining)
        write(c, state)
    }
}

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        try {
            when (intent.action) {
                "lifeos.fire" -> ReminderRuntime.fire(context, intent)
                "lifeos.completed", "lifeos.dismissed", "lifeos.snoozed" -> ReminderRuntime.act(context, intent)
                else -> ReminderRuntime.recovery(context, intent.action == Intent.ACTION_TIMEZONE_CHANGED || intent.action == Intent.ACTION_TIME_CHANGED)
            }
        } catch (e: Exception) {
            // Retain encrypted state. Never replace corrupt or inaccessible data with an empty schedule.
            android.util.Log.e("LifeOS", "Reminder operation failed: ${e.javaClass.simpleName}")
        }
    }
}

class AlarmService : Service() {
    companion object { var activeId: String? = null; var activeRevision = 0; var activeEpoch = 0L }
    private var player: MediaPlayer? = null
    private var vibration: Vibrator? = null
    override fun onBind(intent: Intent?) = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val raw = intent?.getStringExtra("entry") ?: return START_NOT_STICKY
        val e = JSONObject(raw)
        activeId = e.getString("id"); activeRevision = e.getInt("revision"); activeEpoch = intent.getLongExtra("epoch", 0)
        try { startForeground(9001, ReminderRuntime.notification(this, e, intent.getLongExtra("epoch", 0))) }
        catch (_: RuntimeException) { stopSelf(); return START_NOT_STICKY }
        try {
            player?.release()
            if (ReminderRuntime.canSound(this)) player = MediaPlayer().apply {
                setWakeMode(this@AlarmService, PowerManager.PARTIAL_WAKE_LOCK)
                setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build())
                setDataSource(this@AlarmService, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM))
                isLooping = true; prepare(); start()
            }
            vibration = if (ReminderRuntime.canVibrate(this)) getSystemService(Context.VIBRATOR_SERVICE) as Vibrator else null
            if (Build.VERSION.SDK_INT >= 26) vibration?.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 400, 600), 0))
            else { @Suppress("DEPRECATION") vibration?.vibrate(longArrayOf(0, 400, 600), 0) }
        } catch (_: Exception) { }
        // A bounded foreground alert; the pending notification keeps dismissal and snooze accessible.
        Handler(Looper.getMainLooper()).postDelayed({ stopSelf(startId) }, 10 * 60 * 1000L)
        return START_NOT_STICKY
    }
    @Suppress("DEPRECATION")
    override fun onDestroy() { activeId = null; player?.release(); vibration?.cancel(); stopForeground(true); super.onDestroy() }
}
