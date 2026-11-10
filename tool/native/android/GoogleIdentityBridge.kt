package app.lifeos.lifeos

import android.app.Activity
import android.os.CancellationSignal
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CredentialManagerCallback
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetCredentialResponse
import androidx.credentials.exceptions.ClearCredentialException
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executor

/** Native Google account chooser. No WebView, token persistence or token logging. */
class GoogleIdentityBridge(private val activity: Activity) {
    private val manager = CredentialManager.create(activity)
    private val executor = Executor { action -> activity.runOnUiThread(action) }
    private var active: CancellationSignal? = null

    fun signIn(clientId: String, nonce: String, result: MethodChannel.Result) {
        if (active != null) { result.error("client_busy", null, null); return }
        if (!clientId.matches(Regex("[a-zA-Z0-9_-]{8,200}\\.apps\\.googleusercontent\\.com")) ||
            !nonce.matches(Regex("[a-zA-Z0-9_-]{43}"))) {
            result.error("google_invalid", null, null); return
        }
        val option = GetSignInWithGoogleOption.Builder(clientId).setNonce(nonce).build()
        val request = GetCredentialRequest.Builder().addCredentialOption(option).build()
        val cancellation = CancellationSignal()
        active = cancellation
        try {
            manager.getCredentialAsync(activity, request, cancellation, executor,
                object : CredentialManagerCallback<GetCredentialResponse, GetCredentialException> {
                    override fun onResult(value: GetCredentialResponse) {
                        active = null
                        try {
                            val credential = value.credential
                            require(credential is CustomCredential &&
                                credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL)
                            val token = GoogleIdTokenCredential.createFrom(credential.data).idToken
                            require(token.length in 100..16384)
                            result.success(token)
                        } catch (_: Exception) { result.error("google_invalid", null, null) }
                    }
                    override fun onError(error: GetCredentialException) {
                        active = null
                        val code = when (error) {
                            is GetCredentialCancellationException -> "google_cancelled"
                            is NoCredentialException -> "google_no_account"
                            else -> "google_unavailable"
                        }
                        result.error(code, null, null)
                    }
                })
        } catch (_: Exception) { active = null; result.error("google_unavailable", null, null) }
    }

    fun cancel() { active?.cancel() }

    fun signOut(result: MethodChannel.Result) {
        cancel()
        manager.clearCredentialStateAsync(ClearCredentialStateRequest(), null, executor,
            object : CredentialManagerCallback<Void?, ClearCredentialException> {
                override fun onResult(value: Void?) { result.success(null) }
                override fun onError(error: ClearCredentialException) {
                    result.error("google_unavailable", null, null)
                }
            })
    }
}
