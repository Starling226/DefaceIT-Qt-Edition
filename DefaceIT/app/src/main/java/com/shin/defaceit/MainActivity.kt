package com.shin.defaceit

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.shin.defaceit.ui.theme.DefaceITTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DefaceITTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    MainScreen()
                }
            }
        }
    }
}

@Composable
fun MainScreen() {
    var language by remember { mutableStateOf("en") }
    val texts = Languages.texts[language] ?: Languages.texts["en"]!!
    
    var inputVideoUri by remember { mutableStateOf<Uri?>(null) }
    var blurStrength by remember { mutableFloatStateOf(51f) }
    var confidence by remember { mutableFloatStateOf(0.10f) }
    var detectFaces by remember { mutableStateOf(true) }
    var pitchShift by remember { mutableFloatStateOf(0f) }
    var processing by remember { mutableStateOf(false) }
    var progress by remember { mutableFloatStateOf(0f) }
    var statusText by remember { mutableStateOf(texts["ready"]) }
    var videoBlurService by remember { mutableStateOf<VideoBlurService?>(null) }
    var showSecurityDialog by remember { mutableStateOf(false) }
    
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    
    val inputPicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        inputVideoUri = uri
    }
    
    var notificationPermissionGranted by remember { mutableStateOf(
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || 
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    ) }
    
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        notificationPermissionGranted = isGranted
    }

    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = texts["title"] ?: "DefaceIT",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 16.dp)
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        VideoInputSection(
            inputVideoUri = inputVideoUri,
            onInputClick = { inputPicker.launch("video/*") },
            texts = texts
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        SettingsSection(
            blurStrength = blurStrength,
            onBlurStrengthChange = { blurStrength = it },
            confidence = confidence,
            onConfidenceChange = { confidence = it },
            detectFaces = detectFaces,
            onDetectFacesChange = { detectFaces = it },
            pitchShift = pitchShift,
            onPitchShiftChange = { pitchShift = it },
            texts = texts
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        ProcessingSection(
            processing = processing,
            progress = progress,
            statusText = statusText ?: "",
            onStart = {
                if (inputVideoUri == null) {
                    statusText = texts["error_no_input"]
                    return@ProcessingSection
                }
                
                // Request notification permission if needed (Android 13+)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && 
                    !notificationPermissionGranted) {
                    notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    return@ProcessingSection
                }
                
                processing = true
                statusText = "Processing..."
                
                val service = VideoBlurService(
                    context = context,
                    blurStrength = blurStrength.toInt(),
                    blurType = "gaussian",
                    confidence = confidence,
                    detectFaces = detectFaces,
                    pitchShift = pitchShift
                )
                videoBlurService = service
                
                scope.launch(Dispatchers.IO) {
                    val outputFile = File(context.getExternalFilesDir(null), "output_${System.currentTimeMillis()}.mp4")
                    outputFile.parentFile?.mkdirs()
                    
                    val result = service.processVideo(
                        inputUri = inputVideoUri!!,
                        onProgress = { prog, status ->
                            scope.launch(Dispatchers.Main) {
                                progress = prog
                                statusText = status
                            }
                        }
                    )
                    
                    scope.launch(Dispatchers.Main) {
                        processing = false
                        if (result.isSuccess) {
                            val savedPath = result.getOrNull()
                            statusText = "${texts["success_complete"] ?: "Complete!"}\nSaved to: $savedPath"
                            // Show security check dialog
                            showSecurityDialog = true
                        } else {
                            statusText = "Error: ${result.exceptionOrNull()?.message ?: "Unknown error"}"
                        }
                    }
                }
            },
            onCancel = {
                videoBlurService?.cancel()
                processing = false
                statusText = texts["ready"]
            },
            texts = texts
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        CreditsSection(credits = Languages.credits, texts = texts)
    }
    
    // Security check dialog
    if (showSecurityDialog) {
        AlertDialog(
            onDismissRequest = { showSecurityDialog = false },
            title = {
                Text(
                    text = texts["security_check_title"] ?: "Security Check Required",
                    fontWeight = FontWeight.Bold
                )
            },
            text = {
                Text(
                    text = texts["security_check_message"] ?: "Please DOUBLE CHECK the processed video for any remaining faces or sensitive information before sharing or publishing.\n\nFace detection may not catch all faces, especially in challenging conditions (poor lighting, angles, occlusions). Your security is important!",
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = { showSecurityDialog = false }
                ) {
                    Text(text = texts["security_check_understood"] ?: "I Understand")
                }
            }
        )
    }
}

@Composable
fun LanguageSelector(
    language: String,
    onLanguageChange: (String) -> Unit,
    texts: Map<String, String>
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = texts["language"] ?: "Language:")
        Row {
            TextButton(onClick = { onLanguageChange("en") }) {
                Text(text = texts["english"] ?: "English")
            }
        }
    }
}

@Composable
fun VideoInputSection(
    inputVideoUri: Uri?,
    onInputClick: () -> Unit,
    texts: Map<String, String>
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = texts["input_video"] ?: "Input Video:", modifier = Modifier.weight(1f))
            Button(onClick = onInputClick) {
                Text(text = texts["browse"] ?: "Browse...")
            }
        }
        if (inputVideoUri != null) {
            Text(
                text = inputVideoUri.toString().takeLast(30),
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(start = 8.dp)
            )
        }
        
    }
}

@Composable
fun SettingsSection(
    blurStrength: Float,
    onBlurStrengthChange: (Float) -> Unit,
    confidence: Float,
    onConfidenceChange: (Float) -> Unit,
    detectFaces: Boolean,
    onDetectFacesChange: (Boolean) -> Unit,
    pitchShift: Float,
    onPitchShiftChange: (Float) -> Unit,
    texts: Map<String, String>
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = texts["settings"] ?: "Settings",
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        
        Text(text = "${texts["blur_strength"]} ${blurStrength.toInt()}")
        Slider(
            value = blurStrength,
            onValueChange = onBlurStrengthChange,
            valueRange = 1f..101f,
            steps = 49
        )
        
        Text(text = "${texts["confidence"]} ${String.format("%.2f", confidence)}")
        Slider(
            value = confidence,
            onValueChange = onConfidenceChange,
            valueRange = 0.1f..1f
        )
        
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = detectFaces, onCheckedChange = onDetectFacesChange)
            Text(text = texts["faces"] ?: "Faces")
        }
        
        Text(text = "${texts["pitch_semitones"]} ${String.format("%.1f", pitchShift)}")
        Slider(
            value = pitchShift,
            onValueChange = onPitchShiftChange,
            valueRange = -12f..12f
        )
    }
}

@Composable
fun ProcessingSection(
    processing: Boolean,
    progress: Float,
    statusText: String,
    onStart: () -> Unit,
    onCancel: () -> Unit,
    texts: Map<String, String>
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(text = "${texts["progress"]} $statusText")
        LinearProgressIndicator(
            progress = progress / 100f,
            modifier = Modifier.fillMaxWidth()
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            Button(
                onClick = onStart,
                enabled = !processing
            ) {
                Text(text = texts["start_processing"] ?: "Start Processing")
            }
            if (processing) {
                Button(onClick = onCancel) {
                    Text(text = texts["cancel"] ?: "Cancel")
                }
            }
        }
    }
}

@Composable
fun CreditsSection(credits: Map<String, String>, texts: Map<String, String>) {
    val context = LocalContext.current
    
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Made with ❤️ by ${credits["developer"]}",
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        Row(
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextButton(onClick = {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(credits["website"] ?: "")))
            }) {
                Text("Website", fontSize = 13.sp)
            }
            Text("•", color = MaterialTheme.colorScheme.outline)
            TextButton(onClick = {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(credits["telegram"] ?: "")))
            }) {
                Text("Telegram", fontSize = 13.sp)
            }
        }
        
        Row(
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextButton(onClick = {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(credits["donate_crypto"] ?: "")))
            }) {
                Text("Donate (Crypto)", fontSize = 13.sp)
            }
            Text("•", color = MaterialTheme.colorScheme.outline)
            TextButton(onClick = {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(credits["donate_card"] ?: "")))
            }) {
                Text("Donate (Card)", fontSize = 13.sp)
            }
        }
    }
}

@Composable
fun ClickableLink(text: String, label: String) {
    val context = LocalContext.current
    TextButton(
        onClick = {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(text))
            context.startActivity(intent)
        },
        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 0.dp)
    ) {
        Text(text = label, color = MaterialTheme.colorScheme.primary, fontSize = 12.sp)
    }
}
